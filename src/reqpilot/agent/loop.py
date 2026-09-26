"""Goal-driven agent loop.

The loop is the part a fixed workflow cannot express: the model observes the
workspace, picks tools, and keeps working until an objective is met. Two rules
keep it honest. The step budget ends the run instead of looping forever, and the
completion claim is never trusted on its own, because a verifier on the program
side re-checks the workspace before the run can be marked completed.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from reqpilot.agent.context import ContextManager
from reqpilot.agent.sandbox import WorkspaceSandbox
from reqpilot.agent.tools import ToolRegistry, ToolSpec
from reqpilot.models import (
    AgentGoal,
    AgentRun,
    StepTrace,
    ToolCallTrace,
)

GOAL_COMPLETE_TOOL = "goal_complete"
REMEMBER_TOOL = "remember"
WRITE_TOOLS = ("write", "edit", "append")
KNOWN_PROVIDER_NAMES = ("mock", "llm", "scripted")
Verifier = Callable[[], tuple[bool, list[str]]]

SYSTEM_PROMPT = """你是需求工程 Agent，在一个受限工作区里通过调用工具完成目标。

目标：{goal}

工作区根目录：{root}
工作区现有文件：
{listing}

可用工具：
{tools}

工作规则：
1. 用 read 看内容，用 grep 定位关键行。清单类文件可能很长，先用 grep 拿到需要的问题编号再动手。
2. 需要改文件时用 write、append 或 edit；bash 只能执行只读命令，管道和重定向都不可用。
3. 结论必须来自工具输出，不要凭记忆编造文件内容。
4. 单次工具参数有输出长度上限。要写长文件时先 write 写第一段，再用 append 分批追加，每次不超过约 1500 字。
5. 不要无限收集信息。信息够了就产出交付物，交付物是完成目标的唯一证据。
6. 目标达成后调用 {goal_tool} 声明完成。程序会独立校验目标，你的声明只是触发校验。
7. 值得跨运行保留的结论用 {remember_tool} 写入长期记忆。
"""


@dataclass
class AgentLoopResult:
    """Everything one goal run produced."""

    run: AgentRun
    goal: AgentGoal
    transcript: list[dict]
    checks: list[str] = field(default_factory=list)


class AgentLoop:
    """Runs one goal to completion, a step limit, or a failure."""

    def __init__(
        self,
        provider,
        sandbox: WorkspaceSandbox,
        goal_text: str,
        *,
        max_steps: int = 8,
        verifier: Verifier | None = None,
        context: ContextManager | None = None,
        registry: ToolRegistry | None = None,
        budget_tokens: int = 16000,
        max_tool_calls_per_step: int = 4,
        stall_after_steps: int = 2,
    ) -> None:
        self.provider = provider
        self.sandbox = sandbox
        self.goal_text = goal_text
        self.max_steps = max_steps
        self.verifier = verifier
        self.context = context or ContextManager(
            sandbox.root,
            budget_tokens=budget_tokens,
            summarizer=getattr(provider, "summarize", None),
        )
        self.budget_tokens = budget_tokens
        self.max_tool_calls_per_step = max_tool_calls_per_step
        self.stall_after_steps = stall_after_steps
        self.registry = registry or ToolRegistry(
            sandbox,
            extra_specs=[
                ToolSpec(
                    name=REMEMBER_TOOL,
                    description="把一条需要跨运行记住的结论写入工作区的长期记忆文件。",
                    parameters={
                        "type": "object",
                        "properties": {"note": {"type": "string", "description": "要记住的结论"}},
                        "required": ["note"],
                    },
                    handler=lambda args: self.context.remember(
                        str(args.get("note", "")).strip()
                    ),
                )
            ],
        )

    # ------------------------------------------------------------------ run
    def run(self) -> AgentLoopResult:
        self.context.add("system", self._system_prompt())
        memory = self.context.memory_text()
        memory_block = f"\n\n长期记忆（上次运行留下）：\n{memory}" if memory else ""
        self.context.add("user", f"开始执行目标。{memory_block}")

        run = AgentRun(provider=_provider_name(self.provider))
        goal = AgentGoal(text=self.goal_text, max_steps=self.max_steps)
        tools = self.registry.openai_tools()
        traces: list[ToolCallTrace] = []
        step_traces: list[StepTrace] = []
        steps_without_write = 0

        for step in range(1, self.max_steps + 1):
            goal.steps_used = step
            self.context.maybe_compress()
            start = time.monotonic()
            try:
                decision = self.provider.plan_step(self.context.messages, tools)
            except Exception as exc:  # noqa: BLE001 - one bad step must not hide the trace
                step_traces.append(
                    StepTrace(
                        step=f"agent:{step}",
                        provider=run.provider,
                        ok=False,
                        duration_ms=_ms(start),
                        error=str(exc),
                    )
                )
                run.errors.append(f"agent:{step}: {exc}")
                goal.status = "failed"
                break

            step_traces.append(
                StepTrace(
                    step=f"agent:{step}",
                    provider=run.provider,
                    ok=True,
                    duration_ms=_ms(start),
                )
            )
            calls = list(decision.tool_calls)
            claim = decision.claim_goal_complete or any(
                call.name == GOAL_COMPLETE_TOOL for call in calls
            )
            self.context.add(
                "assistant",
                decision.thought or "（本步没有说明）",
                planned_tools=[call.name for call in calls],
            )

            if decision.truncated:
                # A truncated step usually means one tool argument was a whole
                # file, so its JSON never closed. Executing it would write
                # half a document; ask for smaller pieces instead.
                self.context.add(
                    "user",
                    "上一步的输出因为长度上限被截断，工具参数不完整，本次调用没有执行。"
                    "请把内容拆小：先用 write 写第一段，其余用 append 分批追加，"
                    "每次不超过约 1500 字。",
                )
                step_traces[-1] = step_traces[-1].model_copy(
                    update={"ok": False, "error": "truncated"}
                )
                run.fallbacks.append(f"agent:{step}: truncated output, calls skipped")
                continue

            if claim:
                goal.completion_claimed = True
                passed, checks = self._verify()
                goal.checks = checks
                if passed:
                    goal.completion_verified = True
                    goal.status = "completed"
                    self.context.add("user", "程序侧验收通过，目标完成。")
                    break
                self.context.add(
                    "user",
                    "程序侧验收未通过，请继续用工具修复：\n" + "\n".join(checks),
                )

            pending = [call for call in calls if call.name != GOAL_COMPLETE_TOOL]
            if not pending:
                if not claim:
                    self.context.add("user", "你本步没有调用任何工具，请继续用工具推进目标。")
                continue

            executed = pending[: self.max_tool_calls_per_step]
            wrote_this_step = False
            for call in executed:
                tool_start = time.monotonic()
                result = self.registry.call(call.name, call.arguments)
                traces.append(
                    ToolCallTrace(
                        step=step,
                        tool=call.name,
                        arguments=call.arguments,
                        ok=result.ok,
                        duration_ms=_ms(tool_start),
                        output_preview=(result.output or result.error or "")[:200],
                        error=result.error,
                    )
                )
                self.context.add_tool_result(
                    call.name, result.output or (result.error or ""), ok=result.ok
                )
                if result.error and not result.output:
                    run.errors.append(f"agent:{step}:{call.name}: {result.error}")
                if call.name in WRITE_TOOLS and result.ok:
                    wrote_this_step = True
            if len(pending) > len(executed):
                skipped = [call.name for call in pending[len(executed) :]]
                self.context.add(
                    "user",
                    f"本步最多执行 {self.max_tool_calls_per_step} 个工具，以下调用被跳过：{skipped}",
                )

            steps_without_write = 0 if wrote_this_step else steps_without_write + 1
            if steps_without_write >= self.stall_after_steps and not goal.completion_claimed:
                self.context.add(
                    "user",
                    f"你已经连续 {steps_without_write} 步只读取、没有修改任何文件，目标仍未满足。"
                    f"剩余步数 {self.max_steps - step}。请立刻用 write 或 edit 产出交付物，"
                    "不要再重复读取已经看过的文件。",
                )
            elif self.max_steps - step <= 2 and not goal.completion_claimed:
                self.context.add(
                    "user",
                    f"剩余步数 {self.max_steps - step}，请优先产出交付物。",
                )

            if not goal.completion_claimed:
                passed, checks = self._verify()
                if passed:
                    goal.checks = checks
                    self.context.add(
                        "user",
                        f"程序侧验收已经通过，请调用 {GOAL_COMPLETE_TOOL} 声明目标完成。",
                    )

        else:
            # The claim is only a trigger; the verifier decides. Running out of
            # steps while the workspace already satisfies the goal is a pass,
            # not a failure, so record it as completed without a claim.
            passed, checks = self._verify()
            if passed:
                goal.status = "completed"
                goal.completion_verified = True
                goal.checks = [
                    *checks,
                    "步数用尽，但程序侧验收已经通过，按完成记录（模型未主动声明）",
                ]
                run.fallbacks.append("goal verified at the step limit without a model claim")
            else:
                goal.status = "step_limit"
                goal.checks = checks

        run.goal = goal
        run.tool_calls = traces
        run.steps = step_traces
        run.completed_at = datetime.now(UTC)
        run.status = "succeeded" if goal.status == "completed" else "failed"
        run.fingerprint = _fingerprint(self.goal_text, goal, traces)
        return AgentLoopResult(
            run=run,
            goal=goal,
            transcript=list(self.context.messages),
            checks=goal.checks,
        )

    # -------------------------------------------------------------- helpers
    def _system_prompt(self) -> str:
        tool_lines = "\n".join(
            f"- {spec['function']['name']}: {spec['function']['description']}"
            for spec in self.registry.openai_tools()
        )
        return SYSTEM_PROMPT.format(
            goal=self.goal_text,
            root=self.sandbox.root,
            listing=self.sandbox.list_dir("."),
            tools=tool_lines,
            goal_tool=GOAL_COMPLETE_TOOL,
            remember_tool=REMEMBER_TOOL,
        )

    def _verify(self) -> tuple[bool, list[str]]:
        if self.verifier is None:
            return True, ["未配置程序侧验收条件，本次仅记录模型的完成声明"]
        return self.verifier()


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _provider_name(provider) -> str:
    """Keep the trace valid even when a custom provider reports an unexpected name."""

    name = str(getattr(provider, "name", "llm"))
    return name if name in KNOWN_PROVIDER_NAMES else "llm"


def _fingerprint(goal_text: str, goal: AgentGoal, traces: list[ToolCallTrace]) -> str:
    canonical = json.dumps(
        {
            "goal": goal_text,
            "status": goal.status,
            "verified": goal.completion_verified,
            "calls": [
                {"step": t.step, "tool": t.tool, "arguments": t.arguments, "ok": t.ok}
                for t in traces
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
