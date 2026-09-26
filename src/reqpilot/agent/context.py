"""Context and memory management for the agent loop.

Tool output grows without bound, so the loop cannot keep appending forever. This
module keeps a token budget, compresses older messages into one summary once the
budget is nearly reached, and stores two things on disk: the full transcript for
audit, and a long-term memory file for facts worth carrying across runs.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

MEMORY_FILE = "MEMORY.md"
SESSION_FILE = "session.jsonl"


def estimate_tokens(text: str) -> int:
    """Cheap CJK-aware token estimate.

    Chinese characters are close to one token each, while Latin text averages
    roughly four characters per token. The estimate only drives a threshold, so
    an approximation is enough and it keeps the loop offline-testable.
    """

    if not text:
        return 0
    cjk = sum(1 for ch in text if "\u3000" <= ch <= "\u9fff" or "\uff00" <= ch <= "\uffef")
    rest = len(text) - cjk
    return cjk + math.ceil(rest / 4)


class ContextManager:
    """Message buffer with a token budget, compression, and a memory file."""

    def __init__(
        self,
        workspace: str | Path | None = None,
        budget_tokens: int = 16000,
        compress_at: float = 0.9,
        keep_recent: int = 4,
        keep_pinned: int = 2,
        summarizer: Callable[[list[dict[str, Any]]], str] | None = None,
    ) -> None:
        self.workspace = Path(workspace).expanduser().resolve() if workspace else None
        self.budget_tokens = budget_tokens
        self.compress_at = compress_at
        self.keep_recent = keep_recent
        # Pinned messages are never compressed. The system prompt and the goal
        # live here: losing the goal to a summary is how a loop drifts.
        self.keep_pinned = max(1, keep_pinned)
        self.summarizer = summarizer
        self.messages: list[dict[str, Any]] = []
        self.compressions = 0
        if self.workspace:
            self.workspace.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------- messages
    def add(self, role: str, content: str, **extra: Any) -> dict[str, Any]:
        message: dict[str, Any] = {"role": role, "content": content}
        message.update(extra)
        self.messages.append(message)
        self._append_session(message)
        return message

    def add_tool_result(self, tool_name: str, content: str, ok: bool = True) -> dict[str, Any]:
        status = "ok" if ok else "error"
        return self.add(
            "user",
            f"[工具 {tool_name} 执行结果 status={status}]\n{content}",
            name=tool_name,
        )

    def total_tokens(self) -> int:
        return sum(estimate_tokens(str(m.get("content", ""))) for m in self.messages)

    def should_compress(self) -> bool:
        return len(self.messages) > self.keep_recent + self.keep_pinned and self.total_tokens() > (
            self.budget_tokens * self.compress_at
        )

    def maybe_compress(self) -> bool:
        if not self.should_compress():
            return False
        cut = max(self.keep_pinned, len(self.messages) - self.keep_recent)
        # Never split an assistant message from the tool results it produced:
        # a retained tool result whose request was dropped makes no sense.
        while cut > self.keep_pinned and (
            self.messages[cut].get("role") == "tool" or self.messages[cut].get("name")
        ):
            cut -= 1
        dropped = self.messages[self.keep_pinned : cut]
        if not dropped:
            return False
        summary = self._summarize(dropped)
        marker = {
            "role": "user",
            "content": (
                f"[上下文压缩] 之前 {len(dropped)} 条消息已折叠为下面的摘要，"
                f"需要细节时请用工具重新读取文件。\n{summary}"
            ),
        }
        self.messages = [*self.messages[: self.keep_pinned], marker, *self.messages[cut:]]
        self.compressions += 1
        return True

    def _summarize(self, dropped: list[dict[str, Any]]) -> str:
        if self.summarizer is not None:
            try:
                return self.summarizer(dropped)
            except Exception as exc:  # noqa: BLE001 - compression must never break the loop
                return self._fallback_summary(dropped) + f"\n（模型摘要失败：{exc}）"
        return self._fallback_summary(dropped)

    @staticmethod
    def _fallback_summary(dropped: list[dict[str, Any]]) -> str:
        tools: list[str] = []
        lines: list[str] = []
        for message in dropped:
            name = message.get("name")
            if name:
                tools.append(str(name))
            text = str(message.get("content", "")).replace("\n", " ")
            lines.append(f"- {message.get('role')}: {text[:80]}")
        tool_note = f"调用过的工具: {', '.join(dict.fromkeys(tools))}" if tools else "没有工具调用"
        return tool_note + "\n" + "\n".join(lines[:20])

    # --------------------------------------------------------------- memory
    def remember(self, note: str) -> str:
        """Append one durable fact to the long-term memory file."""

        if self.workspace is None:
            raise ValueError("未配置工作区，无法写入长期记忆")
        path = self.workspace / MEMORY_FILE
        if not path.exists():
            path.write_text("# 长期记忆\n\n", encoding="utf-8")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"- {note}\n")
        return note

    def memory_text(self, max_chars: int = 1000) -> str:
        if self.workspace is None:
            return ""
        path = self.workspace / MEMORY_FILE
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")[:max_chars]

    def _append_session(self, message: dict[str, Any]) -> None:
        if self.workspace is None:
            return
        path: Path = self.workspace / SESSION_FILE
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(message, ensure_ascii=False) + "\n")
