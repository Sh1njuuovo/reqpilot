import pytest

from reqpilot.agent.sandbox import SandboxViolation, WorkspaceSandbox


@pytest.fixture()
def sandbox(tmp_path):
    return WorkspaceSandbox(tmp_path)


def test_resolve_keeps_paths_inside_workspace(sandbox):
    assert sandbox.resolve("notes/a.md") == sandbox.root / "notes" / "a.md"
    assert sandbox.resolve(".") == sandbox.root


@pytest.mark.parametrize("raw", ["../outside.md", "../../etc/passwd", "/etc/passwd", ""])
def test_resolve_rejects_escapes(sandbox, raw):
    with pytest.raises(SandboxViolation):
        sandbox.resolve(raw)


def test_file_roundtrip(sandbox):
    sandbox.write_text("prd.md", "# PRD\n验收标准：可查询进度\n")
    assert "验收标准" in sandbox.read_text("prd.md")
    sandbox.edit_text("prd.md", "可查询进度", "可查询进度并导出")
    assert "导出" in sandbox.read_text("prd.md")


def test_append_extends_without_overwriting(sandbox):
    sandbox.write_text("prd.md", "第一段\n")
    sandbox.append_text("prd.md", "第二段\n")
    assert sandbox.read_text("prd.md") == "第一段\n第二段\n"


def test_edit_without_match_reports_error(sandbox):
    sandbox.write_text("prd.md", "abc")
    with pytest.raises(SandboxViolation, match="找不到待替换文本"):
        sandbox.edit_text("prd.md", "zzz", "yyy")


def test_read_missing_file_reports_error(sandbox):
    with pytest.raises(SandboxViolation, match="路径不存在"):
        sandbox.read_text("nope.md")


def test_list_dir_skips_noisy_directories(sandbox):
    (sandbox.root / ".git").mkdir()
    sandbox.write_text("prd.md", "x")
    sandbox.write_text(".git/config", "x")
    listing = sandbox.list_dir(".")
    assert "prd.md" in listing
    assert ".git" not in listing


def test_grep_and_find(sandbox):
    sandbox.write_text("issues.json", '[{"id": "ISSUE-001"}]')
    sandbox.write_text("sub/tasks.md", "- T1\n")
    assert "ISSUE-001" in sandbox.grep("ISSUE-\\d+")
    assert "sub/tasks.md" in sandbox.find("*.md")


def test_run_command_allows_readonly_command(sandbox):
    sandbox.write_text("prd.md", "line1\n")
    result = sandbox.run_command("wc -l prd.md")
    assert result.ok
    assert "1 prd.md" in result.stdout


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf .",
        "python -c 'print(1)'",
        "cat /etc/passwd",
        "cat ../../etc/passwd",
        "find . -exec rm {} ;",
        "sort -o out.md prd.md",
    ],
)
def test_run_command_blocks_escapes_and_writes(sandbox, command):
    sandbox.write_text("prd.md", "x\n")
    with pytest.raises(SandboxViolation):
        sandbox.run_command(command)


def test_run_command_has_no_shell_so_pipes_are_plain_arguments(sandbox):
    sandbox.write_text("prd.md", "a\nb\n")
    result = sandbox.run_command("cat prd.md | wc -l")
    # 没有 shell，管道符只会被当成 cat 的文件名，命令整体失败而不是真的串起来
    assert not result.ok
    assert "a" in result.stdout


def test_run_command_truncates_long_output(tmp_path):
    sandbox = WorkspaceSandbox(tmp_path, max_output_chars=20)
    sandbox.write_text("big.txt", "x" * 500)
    result = sandbox.run_command("cat big.txt")
    assert "输出被截断" in result.stdout


def test_failed_command_is_reported_without_raising(sandbox):
    result = sandbox.run_command("grep missing prd.md")
    assert not result.ok
