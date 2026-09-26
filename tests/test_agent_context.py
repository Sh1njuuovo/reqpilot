import json

from reqpilot.agent.context import (
    MEMORY_FILE,
    SESSION_FILE,
    ContextManager,
    estimate_tokens,
)


def test_estimate_tokens_counts_cjk_per_character():
    assert estimate_tokens("需求评审") == 4
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcdefgh") == 2


def test_session_transcript_is_appended(tmp_path):
    context = ContextManager(tmp_path)
    context.add("system", "系统提示")
    context.add("user", "目标")
    lines = (tmp_path / SESSION_FILE).read_text(encoding="utf-8").strip().splitlines()
    assert [json.loads(line)["role"] for line in lines] == ["system", "user"]


def test_compress_folds_old_messages_and_keeps_recent(tmp_path):
    context = ContextManager(tmp_path, budget_tokens=100, keep_recent=2)
    context.add("system", "系统提示")
    context.add("user", "目标：处理评审阻塞问题")
    for index in range(10):
        context.add("user", f"很长的历史消息 {index} " + "内容" * 40)
    context.add("user", "最近一")
    context.add("user", "最近二")

    assert context.maybe_compress() is True
    assert context.compressions == 1
    assert context.messages[0]["role"] == "system"
    assert context.messages[1]["content"] == "目标：处理评审阻塞问题"
    assert "上下文压缩" in context.messages[2]["content"]
    assert context.messages[-1]["content"] == "最近二"
    assert context.total_tokens() < 100 * 10


def test_pinned_messages_survive_repeated_compression(tmp_path):
    context = ContextManager(tmp_path, budget_tokens=100, keep_recent=1)
    context.add("system", "系统提示")
    context.add("user", "目标：产出 review-fixes.md")
    for index in range(30):
        context.add("user", f"第 {index} 段观察记录 " + "内容" * 60)
        context.maybe_compress()

    # 目标和系统提示被钉住，连续压缩不会把它们折进摘要
    assert context.messages[0]["content"] == "系统提示"
    assert context.messages[1]["content"] == "目标：产出 review-fixes.md"
    assert context.compressions > 1


def test_compress_never_orphans_tool_results(tmp_path):
    context = ContextManager(tmp_path, budget_tokens=1, keep_recent=2, keep_pinned=2)
    context.add("system", "系统提示")
    context.add("user", "目标")
    context.add("assistant", "我要读文件")
    context.add_tool_result("read", "文件内容" * 60)
    context.add("user", "又一条很长的观察 " + "内容" * 60)
    context.add("user", "继续")

    assert context.maybe_compress() is True
    # 保留窗口不能以工具结果开头，否则读到的内容没有对应的调用
    assert not context.messages[2].get("name")


def test_compress_uses_summarizer_when_available(tmp_path):
    context = ContextManager(
        tmp_path,
        budget_tokens=10,
        keep_recent=1,
        summarizer=lambda dropped: f"摘要 {len(dropped)} 条",
    )
    context.add("system", "系统提示")
    for index in range(5):
        context.add("user", f"消息 {index}" * 20)
    assert context.maybe_compress() is True
    assert "摘要" in context.messages[2]["content"]
    assert context.messages[0]["content"] == "系统提示"


def test_summarizer_failure_falls_back_instead_of_breaking(tmp_path):
    def boom(_dropped):
        raise RuntimeError("summarizer down")

    context = ContextManager(tmp_path, budget_tokens=10, keep_recent=1, summarizer=boom)
    context.add("system", "系统提示")
    for index in range(5):
        context.add("user", f"消息 {index}" * 20)
    assert context.maybe_compress() is True
    assert "模型摘要失败" in context.messages[2]["content"]


def test_remember_writes_long_term_memory(tmp_path):
    context = ContextManager(tmp_path)
    context.remember("本项目金额字段必须精确到分")
    assert "金额字段" in context.memory_text()
    assert (tmp_path / MEMORY_FILE).exists()


def test_remember_requires_workspace():
    context = ContextManager()
    try:
        context.remember("x")
    except ValueError as exc:
        assert "工作区" in str(exc)
    else:  # pragma: no cover - 明确失败比静默通过更有价值
        raise AssertionError("缺少工作区时应当报错")
