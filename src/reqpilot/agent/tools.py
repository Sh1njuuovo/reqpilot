"""General-purpose tool set, deliberately small.

The set follows one rule: keep the handful of primitives that generalise across
tasks instead of adding a bespoke function per feature. Reading, searching and
inspecting the workspace cover most of what the agent needs; writes go through
two explicit tools so every mutation of the workspace stays auditable.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from reqpilot.agent.sandbox import SandboxViolation, WorkspaceSandbox


@dataclass(frozen=True)
class ToolResult:
    """Outcome of a single tool call."""

    name: str
    ok: bool
    output: str
    error: str | None = None


@dataclass(frozen=True)
class ToolSpec:
    """A tool the model is allowed to call."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[dict[str, Any]], str]


def _require_str(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SandboxViolation(f"参数 {key} 必须是非空字符串")
    return value


def _optional_int(arguments: dict[str, Any], key: str, default: int) -> int:
    value = arguments.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SandboxViolation(f"参数 {key} 必须是正整数")
    return value


class ToolRegistry:
    """Holds the tool specs and dispatches calls into the sandbox."""

    def __init__(
        self, sandbox: WorkspaceSandbox, extra_specs: list[ToolSpec] | None = None
    ) -> None:
        self.sandbox = sandbox
        specs = self._build() + list(extra_specs or [])
        self._tools: dict[str, ToolSpec] = {spec.name: spec for spec in specs}

    def _build(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="ls",
                description="列出工作区某个目录下的文件与子目录。",
                parameters={
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "目录路径，默认当前目录"}},
                },
                handler=lambda args: self.sandbox.list_dir(args.get("path", ".")),
            ),
            ToolSpec(
                name="read",
                description="读取工作区内某个文本文件的内容，超长会自动截断。",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "max_chars": {"type": "integer", "description": "最多读取的字符数"},
                    },
                    "required": ["path"],
                },
                handler=lambda args: self.sandbox.read_text(
                    _require_str(args, "path"),
                    args.get("max_chars") if isinstance(args.get("max_chars"), int) else None,
                ),
            ),
            ToolSpec(
                name="write",
                description="把内容整体写入工作区内的文件，已存在则覆盖。",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "content": {
                            "type": "string",
                            "description": "完整文件内容；内容较长时先写第一段，其余用 append 分批追加",
                        },
                    },
                    "required": ["path", "content"],
                },
                handler=lambda args: self.sandbox.write_text(
                    _require_str(args, "path"), _require_str(args, "content")
                ),
            ),
            ToolSpec(
                name="append",
                description=(
                    "把内容追加到文件末尾。内容较长时用它分批写入，避免单次输出被长度上限截断。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "content": {"type": "string", "description": "要追加的内容，一次别超过约 1500 字"},
                    },
                    "required": ["path", "content"],
                },
                handler=lambda args: self.sandbox.append_text(
                    _require_str(args, "path"), _require_str(args, "content")
                ),
            ),
            ToolSpec(
                name="edit",
                description="在文件中把一段旧文本替换为新文本，找不到旧文本会报错。",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "文件路径"},
                        "old": {"type": "string", "description": "待替换的原文"},
                        "new": {"type": "string", "description": "替换后的文本"},
                        "count": {"type": "integer", "description": "最多替换几处，默认 1"},
                    },
                    "required": ["path", "old", "new"],
                },
                handler=lambda args: self.sandbox.edit_text(
                    _require_str(args, "path"),
                    _require_str(args, "old"),
                    args.get("new") if isinstance(args.get("new"), str) else "",
                    _optional_int(args, "count", 1),
                ),
            ),
            ToolSpec(
                name="grep",
                description="在工作区文件里按正则搜索，返回 文件:行号: 内容。",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "正则表达式"},
                        "path": {"type": "string", "description": "搜索起点，默认当前目录"},
                        "max_hits": {"type": "integer", "description": "最多返回多少条，默认 50"},
                    },
                    "required": ["pattern"],
                },
                handler=lambda args: self.sandbox.grep(
                    _require_str(args, "pattern"),
                    args.get("path", "."),
                    _optional_int(args, "max_hits", 50),
                ),
            ),
            ToolSpec(
                name="find",
                description="按文件名通配符查找工作区内的文件。",
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "文件名通配符，例如 *.md"},
                        "path": {"type": "string", "description": "查找起点，默认当前目录"},
                    },
                    "required": ["pattern"],
                },
                handler=lambda args: self.sandbox.find(
                    _require_str(args, "pattern"), args.get("path", ".")
                ),
            ),
            ToolSpec(
                name="bash",
                description=(
                    "在工作区内执行一条只读 shell 命令，例如 wc -l、grep -n、ls -la。"
                    "不允许管道、重定向、命令串联，也不允许任何写操作。"
                ),
                parameters={
                    "type": "object",
                    "properties": {"command": {"type": "string", "description": "要执行的命令"}},
                    "required": ["command"],
                },
                handler=self._run_bash,
            ),
        ]

    def _run_bash(self, args: dict[str, Any]) -> str:
        result = self.sandbox.run_command(_require_str(args, "command"))
        if result.ok:
            return result.stdout or "（命令成功，无输出）"
        return f"命令退出码 {result.returncode}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"

    # -------------------------------------------------------------- interface
    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def openai_tools(self) -> list[dict[str, Any]]:
        """Render the specs in the OpenAI ``tools`` parameter format."""

        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self._tools.values()
        ]

    def call(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        spec = self._tools.get(name)
        if spec is None:
            return ToolResult(
                name=name,
                ok=False,
                output="",
                error=f"未知工具 {name}；可用工具: {', '.join(self.names)}",
            )
        try:
            output = spec.handler(dict(arguments or {}))
        except SandboxViolation as exc:
            return ToolResult(name=name, ok=False, output="", error=str(exc))
        except (OSError, ValueError) as exc:
            return ToolResult(name=name, ok=False, output="", error=f"{type(exc).__name__}: {exc}")
        return ToolResult(name=name, ok=True, output=output)
