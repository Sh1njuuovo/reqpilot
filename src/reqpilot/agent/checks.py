"""Program-side acceptance checks for the review-repair goal.

The model is allowed to claim that the goal is done, but the claim only triggers
this verifier. Every check below reads the workspace directly, so a run can only
be marked completed when the files really satisfy the goal.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from reqpilot.agent.sandbox import WorkspaceSandbox

REVIEW_FIX_FILE = "review-fixes.md"
ISSUES_FILE = "issues.json"
TASKS_FILE = "tasks.md"
BLOCKING_SEVERITIES = ("critical", "major")
# A stub file that only carries a title is not an answer, so require some content.
MIN_CONTENT_CHARS = 10

REVIEW_FIX_GOAL = (
    "处理本次需求评审中的阻塞问题：对 issues.json 里 severity 为 critical 或 major 的每一条问题，"
    "在 review-fixes.md 中给出处理结论，并确认 tasks.md 已经覆盖整改任务。"
)


def review_fix_verifier(sandbox: WorkspaceSandbox) -> Callable[[], tuple[bool, list[str]]]:
    """Build the verifier used by ``reqpilot agent``."""

    def verify() -> tuple[bool, list[str]]:
        checks: list[str] = []
        failures: list[str] = []

        # 1. the issue list must be readable
        issues_path = sandbox.root / ISSUES_FILE
        issues: list[dict] = []
        if not issues_path.exists():
            failures.append(f"缺少 {ISSUES_FILE}，无法核对问题清单")
        else:
            try:
                loaded = json.loads(issues_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                failures.append(f"{ISSUES_FILE} 不是合法 JSON: {exc}")
            else:
                if isinstance(loaded, list):
                    issues = [item for item in loaded if isinstance(item, dict)]
                    checks.append(f"{ISSUES_FILE} 可读，共 {len(issues)} 条问题")
                else:
                    failures.append(f"{ISSUES_FILE} 结构不是列表")

        # 2. the fix record must exist
        fix_path = sandbox.root / REVIEW_FIX_FILE
        fix_text = fix_path.read_text(encoding="utf-8") if fix_path.exists() else ""
        if len(fix_text.strip()) < MIN_CONTENT_CHARS:
            failures.append(f"{REVIEW_FIX_FILE} 缺失或内容过短，需要逐条给出处理结论")
        else:
            checks.append(f"{REVIEW_FIX_FILE} 已存在（{len(fix_text)} 字符）")

        # 3. every blocking issue must be answered
        blocking = [i for i in issues if str(i.get("severity")) in BLOCKING_SEVERITIES]
        if not blocking:
            checks.append("问题清单里没有 critical/major 问题，无需逐条整改")
        unanswered = [str(i.get("id", "?")) for i in blocking if str(i.get("id", "")) not in fix_text]
        if unanswered:
            failures.append(
                f"{REVIEW_FIX_FILE} 未覆盖 {len(unanswered)} 条阻塞问题: " + ", ".join(unanswered)
            )
        elif blocking:
            checks.append(f"阻塞问题已全部覆盖（{len(blocking)} 条）")

        # 4. the task list must still be deliverable
        tasks_path = sandbox.root / TASKS_FILE
        tasks_text = tasks_path.read_text(encoding="utf-8") if tasks_path.exists() else ""
        if len(tasks_text.strip()) < MIN_CONTENT_CHARS:
            failures.append(f"{TASKS_FILE} 缺失或内容过短")
        else:
            checks.append(f"{TASKS_FILE} 已存在（{len(tasks_text)} 字符）")

        return (not failures), checks + [f"未通过：{item}" for item in failures]

    return verify
