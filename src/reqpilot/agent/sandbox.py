"""Workspace sandbox: the single place that decides what a tool may touch.

Every file tool goes through :meth:`WorkspaceSandbox.resolve`, so all paths are
jailed into one workspace directory. Shell access is limited to a read-only
command allowlist that is executed without a shell, which removes pipes,
redirection and command chaining as escape routes.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

READONLY_COMMANDS = frozenset(
    {
        "cat",
        "cut",
        "du",
        "echo",
        "find",
        "grep",
        "head",
        "ls",
        "nl",
        "pwd",
        "sort",
        "tail",
        "tr",
        "uniq",
        "wc",
    }
)

# Flags that turn an allowlisted read-only command into a writer or an executor.
BLOCKED_FLAGS: dict[str, frozenset[str]] = {
    "find": frozenset(
        {
            "-delete",
            "-exec",
            "-execdir",
            "-fls",
            "-fprint",
            "-fprint0",
            "-fprintf",
            "-ok",
            "-okdir",
        }
    ),
    "sort": frozenset({"-o", "--output"}),
}

SKIP_DIRS = frozenset({".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"})
DEFAULT_MAX_OUTPUT_CHARS = 4000


class SandboxViolation(RuntimeError):
    """Raised when a tool call leaves the workspace or runs a blocked command."""


@dataclass(frozen=True)
class CommandResult:
    """Result of one sandboxed command execution."""

    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = text[:limit]
    return f"{head}\n...[输出被截断，原始长度 {len(text)} 字符]"


class WorkspaceSandbox:
    """Jails all file and command access to ``root``."""

    def __init__(
        self,
        root: str | Path,
        max_output_chars: int = DEFAULT_MAX_OUTPUT_CHARS,
        command_timeout: float = 10.0,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_output_chars = max_output_chars
        self.command_timeout = command_timeout

    # ---------------------------------------------------------------- paths
    def resolve(self, raw: str, *, must_exist: bool = False) -> Path:
        """Resolve a workspace-relative path, refusing anything outside the jail."""

        if not isinstance(raw, str) or not raw.strip():
            raise SandboxViolation("path 必须是非空字符串")
        candidate = Path(raw).expanduser()
        resolved = candidate.resolve() if candidate.is_absolute() else (self.root / candidate).resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise SandboxViolation(f"路径越出工作区: {raw}")
        if must_exist and not resolved.exists():
            raise SandboxViolation(f"路径不存在: {raw}")
        return resolved

    def relative(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    # ------------------------------------------------------------ file ops
    def read_text(self, raw: str, max_chars: int | None = None) -> str:
        path = self.resolve(raw, must_exist=True)
        if path.is_dir():
            raise SandboxViolation(f"这是目录，不能按文件读取: {raw}")
        text = path.read_text(encoding="utf-8", errors="replace")
        return _truncate(text, max_chars or self.max_output_chars)

    def write_text(self, raw: str, content: str) -> str:
        path = self.resolve(raw)
        if path.exists() and path.is_dir():
            raise SandboxViolation(f"这是目录，不能写入: {raw}")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"已写入 {self.relative(path)}（{len(content)} 字符）"

    def append_text(self, raw: str, content: str) -> str:
        path = self.resolve(raw)
        if path.exists() and path.is_dir():
            raise SandboxViolation(f"这是目录，不能写入: {raw}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(content)
        return f"已追加到 {self.relative(path)}（新增 {len(content)} 字符）"

    def edit_text(self, raw: str, old: str, new: str, count: int = 1) -> str:
        path = self.resolve(raw, must_exist=True)
        text = path.read_text(encoding="utf-8", errors="replace")
        occurrences = text.count(old)
        if occurrences == 0:
            raise SandboxViolation(f"在 {raw} 中找不到待替换文本，请先 read 确认原文")
        replaced = text.replace(old, new, count)
        path.write_text(replaced, encoding="utf-8")
        return f"已替换 {min(occurrences, count)} 处（原文共出现 {occurrences} 次）"

    def list_dir(self, raw: str = ".", limit: int = 200) -> str:
        path = self.resolve(raw, must_exist=True)
        if not path.is_dir():
            raise SandboxViolation(f"不是目录: {raw}")
        entries = []
        for child in sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name)):
            if child.name in SKIP_DIRS:
                continue
            entries.append(f"{child.name}/" if child.is_dir() else child.name)
        if not entries:
            return "（空目录）"
        if len(entries) > limit:
            entries = entries[:limit] + [f"...共 {len(entries)} 项"]
        return "\n".join(entries)

    def grep(self, pattern: str, raw: str = ".", max_hits: int = 50) -> str:
        import re

        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise SandboxViolation(f"正则表达式无效: {exc}") from exc
        base = self.resolve(raw, must_exist=True)
        hits: list[str] = []
        for file in self._iter_files(base):
            text = file.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    hits.append(f"{self.relative(file)}:{lineno}: {line.strip()[:200]}")
                    if len(hits) >= max_hits:
                        return "\n".join(hits) + f"\n...[命中达到上限 {max_hits}]"
        return "\n".join(hits) if hits else "（没有命中）"

    def find(self, pattern: str, raw: str = ".") -> str:
        import fnmatch

        base = self.resolve(raw, must_exist=True)
        matches = [
            self.relative(path) for path in self._iter_files(base) if fnmatch.fnmatch(path.name, pattern)
        ]
        return "\n".join(sorted(matches)) if matches else "（没有匹配文件）"

    def _iter_files(self, base: Path):
        if base.is_file():
            yield base
            return
        for path in sorted(base.rglob("*")):
            if path.is_dir() or any(part in SKIP_DIRS for part in path.parts):
                continue
            yield path

    # ---------------------------------------------------------- shell ops
    def run_command(self, command: str) -> CommandResult:
        """Run one allowlisted, read-only command inside the workspace, without a shell."""

        try:
            argv = shlex.split(command)
        except ValueError as exc:
            raise SandboxViolation(f"命令无法解析: {exc}") from exc
        if not argv:
            raise SandboxViolation("命令为空")
        program = argv[0]
        if program not in READONLY_COMMANDS:
            raise SandboxViolation(
                f"命令 {program} 不在只读白名单内；允许的命令: {', '.join(sorted(READONLY_COMMANDS))}"
            )
        blocked = BLOCKED_FLAGS.get(program, frozenset())
        for token in argv[1:]:
            if token in blocked:
                raise SandboxViolation(f"{program} 的 {token} 参数会写入或执行外部程序，已禁用")
            if token.startswith("-") or token == "":
                continue
            if "/" in token or token == "..":
                self.resolve(token)

        try:
            completed = subprocess.run(
                argv,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=self.command_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise SandboxViolation(f"命令超时（>{self.command_timeout}s）: {command}") from exc
        except OSError as exc:
            raise SandboxViolation(f"命令无法执行: {exc}") from exc
        return CommandResult(
            command=command,
            returncode=completed.returncode,
            stdout=_truncate(completed.stdout, self.max_output_chars),
            stderr=_truncate(completed.stderr, self.max_output_chars),
        )
