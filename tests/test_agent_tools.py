from reqpilot.agent.sandbox import WorkspaceSandbox
from reqpilot.agent.tools import ToolRegistry


def _registry(tmp_path):
    return ToolRegistry(WorkspaceSandbox(tmp_path))


def test_registry_exposes_only_general_tools(tmp_path):
    registry = _registry(tmp_path)
    assert registry.names == ["ls", "read", "write", "append", "edit", "grep", "find", "bash"]


def test_openai_tool_schema_shape(tmp_path):
    tools = _registry(tmp_path).openai_tools()
    assert all(item["type"] == "function" for item in tools)
    read = next(item for item in tools if item["function"]["name"] == "read")
    assert read["function"]["parameters"]["required"] == ["path"]


def test_write_then_read_roundtrip(tmp_path):
    registry = _registry(tmp_path)
    written = registry.call("write", {"path": "prd.md", "content": "# PRD\n"})
    assert written.ok
    read = registry.call("read", {"path": "prd.md"})
    assert read.ok
    assert read.output == "# PRD\n"


def test_append_builds_a_file_in_chunks(tmp_path):
    registry = _registry(tmp_path)
    registry.call("write", {"path": "review-fixes.md", "content": "# 整改结论\n"})
    registry.call("append", {"path": "review-fixes.md", "content": "- ISSUE-001 已补充幂等说明\n"})
    registry.call("append", {"path": "review-fixes.md", "content": "- ISSUE-002 已明确分页上限\n"})

    text = (tmp_path / "review-fixes.md").read_text(encoding="utf-8")
    assert text.count("ISSUE-") == 2
    assert text.startswith("# 整改结论")


def test_append_creates_the_file_when_missing(tmp_path):
    result = _registry(tmp_path).call("append", {"path": "notes.md", "content": "第一条\n"})
    assert result.ok
    assert (tmp_path / "notes.md").read_text(encoding="utf-8") == "第一条\n"


def test_unknown_tool_is_reported_not_raised(tmp_path):
    result = _registry(tmp_path).call("rm_everything", {})
    assert not result.ok
    assert "未知工具" in result.error


def test_bad_arguments_are_reported(tmp_path):
    result = _registry(tmp_path).call("write", {"path": "prd.md"})
    assert not result.ok
    assert "content" in result.error


def test_sandbox_violation_becomes_tool_error(tmp_path):
    result = _registry(tmp_path).call("read", {"path": "../secret.md"})
    assert not result.ok
    assert "越出工作区" in result.error


def test_bash_tool_surfaces_failure(tmp_path):
    result = _registry(tmp_path).call("bash", {"command": "grep nothing missing.md"})
    assert result.ok is True
    assert "命令退出码" in result.output


def test_bash_tool_rejects_non_readonly_command(tmp_path):
    result = _registry(tmp_path).call("bash", {"command": "rm -rf ."})
    assert not result.ok
    assert "只读白名单" in result.error
