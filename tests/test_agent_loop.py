import json

from reqpilot.agent.checks import review_fix_verifier
from reqpilot.agent.loop import AgentLoop
from reqpilot.agent.sandbox import WorkspaceSandbox
from reqpilot.providers.base import ProviderError
from reqpilot.providers.scripted import ScriptedAgentProvider, call, calls, finish

WORKSPACE_FILES = {
    "issues.json": json.dumps(
        [
            {"id": "ISSUE-001", "severity": "critical", "title": "缺少幂等说明"},
            {"id": "ISSUE-002", "severity": "major", "title": "分页上限未定义"},
            {"id": "ISSUE-003", "severity": "minor", "title": "文案不一致"},
        ],
        ensure_ascii=False,
    ),
    "tasks.md": "# 任务清单\n- T1 补齐幂等校验\n- T2 明确分页上限\n",
}


def _sandbox(tmp_path, extra=None):
    files = dict(WORKSPACE_FILES)
    files.update(extra or {})
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return WorkspaceSandbox(tmp_path)


def _loop(sandbox, script, **kwargs):
    return AgentLoop(
        ScriptedAgentProvider(script),
        sandbox,
        kwargs.pop("goal", "处理评审里的阻塞问题"),
        verifier=review_fix_verifier(sandbox),
        **kwargs,
    )


def test_loop_reaches_verified_completion(tmp_path):
    sandbox = _sandbox(tmp_path)
    loop = _loop(
        sandbox,
        [
            call("ls", path="."),
            call("read", path="issues.json"),
            call(
                "write",
                path="review-fixes.md",
                content="# 整改结论\n- ISSUE-001 已补充幂等校验\n- ISSUE-002 已明确分页上限\n",
            ),
            finish("阻塞问题都处理完了"),
        ],
    )
    result = loop.run()

    assert result.goal.status == "completed"
    assert result.goal.completion_claimed is True
    assert result.goal.completion_verified is True
    assert result.goal.steps_used == 4
    assert result.run.status == "succeeded"
    assert [trace.tool for trace in result.run.tool_calls] == ["ls", "read", "write"]
    assert result.run.fingerprint
    assert (sandbox.root / "review-fixes.md").exists()


def test_claim_without_evidence_is_rejected_then_repaired(tmp_path):
    sandbox = _sandbox(tmp_path)
    loop = _loop(
        sandbox,
        [
            finish("我觉得已经完成了"),
            call(
                "write",
                path="review-fixes.md",
                content="# 整改结论\n- ISSUE-001 已补充幂等校验\n- ISSUE-002 已明确分页上限\n",
            ),
            finish("这次确实完成了"),
        ],
    )
    result = loop.run()

    assert result.goal.status == "completed"
    assert result.goal.steps_used == 3
    feedback = [m["content"] for m in result.transcript if "验收未通过" in str(m.get("content"))]
    assert feedback, "验收失败必须把原因回灌给模型"
    assert "review-fixes.md" in feedback[0]


def test_step_limit_marks_run_failed(tmp_path):
    sandbox = _sandbox(tmp_path)
    provider = ScriptedAgentProvider([call("ls")], on_exhausted=call("ls"))
    loop = AgentLoop(
        provider,
        sandbox,
        "处理评审里的阻塞问题",
        max_steps=3,
        verifier=review_fix_verifier(sandbox),
    )
    result = loop.run()

    assert result.goal.status == "step_limit"
    assert result.goal.steps_used == 3
    assert result.run.status == "failed"
    assert provider.calls == 3


def test_step_limit_with_a_satisfied_workspace_counts_as_completed(tmp_path):
    sandbox = _sandbox(
        tmp_path,
        {
            "review-fixes.md": (
                "# 整改结论\n- ISSUE-001 已补充幂等校验\n- ISSUE-002 已明确分页上限\n"
            )
        },
    )
    provider = ScriptedAgentProvider([call("ls")], on_exhausted=call("ls"))
    loop = AgentLoop(
        provider,
        sandbox,
        "处理评审里的阻塞问题",
        max_steps=3,
        verifier=review_fix_verifier(sandbox),
    )
    result = loop.run()

    # 目标由验收决定，模型没声明完成但工作区已满足，就不该判失败
    assert result.goal.status == "completed"
    assert result.goal.completion_claimed is False
    assert result.goal.completion_verified is True
    assert result.run.status == "succeeded"
    assert any("未主动声明" in check for check in result.goal.checks)
    assert any("without a model claim" in f for f in result.run.fallbacks)


def test_provider_failure_is_recorded(tmp_path):
    class Boom:
        name = "boom"

        def plan_step(self, messages, tools):
            raise ProviderError("model down")

    loop = AgentLoop(
        Boom(),
        _sandbox(tmp_path),
        "目标",
        verifier=review_fix_verifier(WorkspaceSandbox(tmp_path)),
    )
    result = loop.run()

    assert result.goal.status == "failed"
    assert result.run.status == "failed"
    assert any("model down" in error for error in result.run.errors)
    assert result.run.provider == "llm"


def test_tool_failure_is_recorded_and_loop_continues(tmp_path):
    sandbox = _sandbox(tmp_path)
    loop = _loop(
        sandbox,
        [
            call("read", path="missing.md"),
            call(
                "write",
                path="review-fixes.md",
                content="# 整改结论\n- ISSUE-001 已补充幂等校验\n- ISSUE-002 已明确分页上限\n",
            ),
            finish("完成"),
        ],
    )
    result = loop.run()

    assert result.goal.status == "completed"
    assert result.run.tool_calls[0].ok is False
    assert any("missing.md" in error for error in result.run.errors)


def test_natural_completion_nudges_model_to_declare(tmp_path):
    sandbox = _sandbox(
        tmp_path,
        {
            "review-fixes.md": (
                "# 整改结论\n- ISSUE-001 已补充幂等校验\n- ISSUE-002 已明确分页上限\n"
            )
        },
    )
    loop = _loop(sandbox, [call("ls"), finish("完成")])
    result = loop.run()

    nudges = [m["content"] for m in result.transcript if "验收已经通过" in str(m.get("content"))]
    assert nudges
    assert result.goal.completion_verified is True


def test_tool_calls_per_step_are_capped(tmp_path):
    sandbox = _sandbox(tmp_path)
    loop = _loop(
        sandbox,
        [calls(*[("ls", {"path": "."})] * 6), finish("完成")],
        max_steps=2,
        max_tool_calls_per_step=2,
    )
    result = loop.run()

    assert len(result.run.tool_calls) == 2
    assert any("被跳过" in str(m.get("content")) for m in result.transcript)


def test_remember_tool_writes_long_term_memory(tmp_path):
    sandbox = _sandbox(tmp_path)
    loop = _loop(
        sandbox,
        [
            call("remember", note="金额字段必须精确到分"),
            call(
                "write",
                path="review-fixes.md",
                content="# 整改结论\n- ISSUE-001 已补充幂等校验\n- ISSUE-002 已明确分页上限\n",
            ),
            finish("完成"),
        ],
    )
    result = loop.run()

    assert result.goal.status == "completed"
    assert "金额字段" in (sandbox.root / "MEMORY.md").read_text(encoding="utf-8")


def test_goal_complete_tool_call_counts_as_claim(tmp_path):
    sandbox = _sandbox(
        tmp_path,
        {
            "review-fixes.md": (
                "# 整改结论\n- ISSUE-001 已补充幂等校验\n- ISSUE-002 已明确分页上限\n"
            )
        },
    )
    loop = _loop(sandbox, [call("goal_complete")])
    result = loop.run()

    assert result.goal.completion_claimed is True
    assert result.goal.completion_verified is True
    assert [trace.tool for trace in result.run.tool_calls] == []


def test_transcript_and_session_file_are_kept(tmp_path):
    sandbox = _sandbox(tmp_path)
    result = _loop(sandbox, [finish("完成")]).run()

    assert result.transcript[0]["role"] == "system"
    assert (sandbox.root / "session.jsonl").exists()


def test_goal_is_pinned_in_the_system_prompt(tmp_path):
    sandbox = _sandbox(tmp_path)
    goal = "把 issues.json 里的阻塞问题写进 review-fixes.md"
    result = _loop(sandbox, [finish("完成")], goal=goal).run()

    # 目标写在系统提示里，压缩上下文时不会把目标折进摘要
    assert goal in result.transcript[0]["content"]
    assert "工作区现有文件" in result.transcript[0]["content"]


def test_stall_nudge_pushes_the_model_to_write(tmp_path):
    sandbox = _sandbox(tmp_path)
    result = _loop(
        sandbox,
        [
            call("ls"),
            call("read", path="issues.json"),
            call("grep", pattern="ISSUE"),
            finish("完成"),
        ],
    ).run()

    nudges = [
        m["content"] for m in result.transcript if "没有修改任何文件" in str(m.get("content"))
    ]
    assert nudges, "连续只读时必须提示模型产出交付物"
    assert "write" in nudges[0]


def test_no_stall_nudge_when_the_model_writes(tmp_path):
    sandbox = _sandbox(tmp_path)
    result = _loop(
        sandbox,
        [
            call("ls"),
            call(
                "write",
                path="review-fixes.md",
                content="# 整改结论\n- ISSUE-001 已补充幂等说明\n- ISSUE-002 已明确分页上限\n",
            ),
            finish("完成"),
        ],
    ).run()

    assert not any("没有修改任何文件" in str(m.get("content")) for m in result.transcript)
    assert result.goal.status == "completed"


def test_remaining_steps_hint_near_the_budget(tmp_path):
    sandbox = _sandbox(tmp_path)
    result = _loop(sandbox, [call("ls"), finish("完成")], max_steps=2).run()

    assert any("剩余步数 1" in str(m.get("content")) for m in result.transcript)


def test_truncated_step_is_not_executed(tmp_path):
    from reqpilot.models import AgentDecision, ToolCallRequest

    sandbox = _sandbox(tmp_path)
    truncated = AgentDecision(
        tool_calls=[
            ToolCallRequest(
                name="write",
                arguments={
                    "path": "review-fixes.md",
                    "content": "# 整改结论\n- ISSUE-001 被截断的半",
                },
            )
        ],
        truncated=True,
    )
    loop = _loop(
        sandbox,
        [
            truncated,
            call(
                "write",
                path="review-fixes.md",
                content="# 整改结论\n- ISSUE-001 已补充幂等说明\n- ISSUE-002 已明确分页上限\n",
            ),
            finish("完成"),
        ],
    )
    result = loop.run()

    # 被截断的一步不能落盘，否则会写出半份文档
    assert not (sandbox.root / "review-fixes.md").exists() or "半" not in (
        sandbox.root / "review-fixes.md"
    ).read_text(encoding="utf-8")
    assert result.run.fallbacks and "truncated" in result.run.fallbacks[0]
    assert any("长度上限被截断" in str(m.get("content")) for m in result.transcript)
    assert result.goal.status == "completed"


def test_provider_summarizer_is_wired_into_the_context(tmp_path):
    class SummarizingProvider(ScriptedAgentProvider):
        def summarize(self, messages):
            return "压缩摘要标记"

    sandbox = _sandbox(tmp_path)
    provider = SummarizingProvider(
        [
            calls(*[("ls", {"path": "."})] * 4),
            calls(*[("ls", {"path": "."})] * 4),
            finish("完成"),
        ]
    )
    loop = AgentLoop(
        provider,
        sandbox,
        "处理阻塞问题",
        max_steps=4,
        verifier=review_fix_verifier(sandbox),
        budget_tokens=1,
    )
    result = loop.run()

    assert any("压缩摘要标记" in str(m.get("content")) for m in result.transcript)
