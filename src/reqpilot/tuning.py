"""Measure review-prompt variants on the golden set and pick a winner.

Tuning a prompt by hand leaves no record of what was tried or why one wording
won. This module runs the existing evaluation for each named variant, applies one
stated selection rule, and writes the comparison to disk so the choice can be
re-checked later.

Selection rule: only variants whose final issue list stays within a per-case
budget are eligible, because the point of the convergence guardrail is that a
human can still read the list. Among the eligible variants, higher issue recall
wins; ties break on a shorter list, then on precision.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from reqpilot.config import project_root
from reqpilot.eval.runner import run_eval
from reqpilot.prompt_variants import REVIEW_PROMPT_VARIANTS, resolve_variant

PROMPT_VARIANT_ENV = "REQPILOT_PROMPT_VARIANT"
DEFAULT_MAX_FINAL_ISSUES = 20


@dataclass
class VariantResult:
    """Aggregated metrics for one prompt variant."""

    variant: str
    success_rate: float
    avg_recall: float
    avg_precision: float
    avg_dedup_rate: float
    avg_final_issues: float
    avg_duration_ms: float
    eligible: bool

    def to_dict(self) -> dict:
        return {
            "variant": self.variant,
            "success_rate": round(self.success_rate, 4),
            "avg_recall": round(self.avg_recall, 4),
            "avg_precision": round(self.avg_precision, 4),
            "avg_dedup_rate": round(self.avg_dedup_rate, 4),
            "avg_final_issues": round(self.avg_final_issues, 2),
            "avg_duration_ms": round(self.avg_duration_ms, 1),
            "eligible": self.eligible,
        }


@dataclass
class TuningReport:
    """Comparison of all measured variants plus the selection outcome."""

    provider: str
    retriever_backend: str
    max_final_issues: int
    results: list[VariantResult]
    best: str
    reason: str
    out_dir: Path

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "retriever_backend": self.retriever_backend,
            "max_final_issues": self.max_final_issues,
            "best": self.best,
            "reason": self.reason,
            "variants": [r.to_dict() for r in self.results],
        }

    def render_markdown(self) -> str:
        lines = [
            "# ReqPilot 提示词变体评测",
            "",
            f"- 生成时间：{datetime.now(UTC).isoformat(timespec='seconds')}",
            f"- provider：`{self.provider}`，检索后端：`{self.retriever_backend}`",
            f"- 问题数预算：每个案例最终不超过 {self.max_final_issues} 条",
            f"- 选中变体：**{self.best}**",
            f"- 选择理由：{self.reason}",
            "",
            "| 变体 | 成功率 | 召回 | 精确率 | 去重率 | 平均最终问题数 | 满足预算 |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for r in self.results:
            lines.append(
                f"| {r.variant} | {r.success_rate:.0%} | {r.avg_recall:.1%} | "
                f"{r.avg_precision:.1%} | {r.avg_dedup_rate:.1%} | "
                f"{r.avg_final_issues:.1f} | {'✓' if r.eligible else '✗'} |"
            )
        lines += [
            "",
            "复现：`uv run reqpilot tune`，逐变体明细落在本目录的 `runs/` 下。",
            "切换运行期变体：`export REQPILOT_PROMPT_VARIANT=<变体名>`。",
        ]
        return "\n".join(lines)


def _select(
    results: list[VariantResult], max_final_issues: int
) -> tuple[str, str]:
    if not results:
        raise ValueError("没有可评测的变体")
    eligible = [r for r in results if r.eligible]
    pool = eligible or results
    best = max(pool, key=lambda r: (r.avg_recall, -r.avg_final_issues, r.avg_precision))
    if eligible:
        reason = (
            f"{len(eligible)}/{len(results)} 个变体把每案例问题数控制在 {max_final_issues} 条以内，"
            f"在其中选择问题召回最高的 {best.variant}"
        )
    else:
        reason = (
            f"没有变体满足 {max_final_issues} 条的问题数预算，退化为按问题召回最高选择 "
            f"{best.variant}，需要继续调整提示词或收敛阈值"
        )
    return best.variant, reason


def tune_review_prompt(
    provider_name: str = "llm",
    retriever_backend: str = "keyword",
    variants: list[str] | None = None,
    cases_dir: str | Path | None = None,
    out_dir: str | Path | None = None,
    max_final_issues: int = DEFAULT_MAX_FINAL_ISSUES,
) -> TuningReport:
    """Run the evaluation once per variant and select the best one."""

    root = project_root()
    out_dir = Path(out_dir or (root / "reports" / "tuning"))
    requested = variants or list(REVIEW_PROMPT_VARIANTS)
    resolved = list(dict.fromkeys(resolve_variant(name) for name in requested))

    previous = os.environ.get(PROMPT_VARIANT_ENV)
    results: list[VariantResult] = []
    try:
        for variant in resolved:
            os.environ[PROMPT_VARIANT_ENV] = variant
            summary = run_eval(
                provider_name=provider_name,
                retriever_backend=retriever_backend,
                cases_dir=cases_dir,
                out_dir=out_dir / "runs" / variant,
            )
            cases = summary.cases
            if not cases:
                raise ValueError(f"变体 {variant} 没有可用的评测用例")
            aggregate = summary.aggregate
            avg_final = sum(c.final_issue_count for c in cases) / len(cases)
            results.append(
                VariantResult(
                    variant=variant,
                    success_rate=aggregate["success_rate"],
                    avg_recall=aggregate["avg_recall"],
                    avg_precision=aggregate["avg_precision"],
                    avg_dedup_rate=aggregate["avg_dedup_rate"],
                    avg_final_issues=avg_final,
                    avg_duration_ms=aggregate["avg_duration_ms"],
                    eligible=avg_final <= max_final_issues,
                )
            )
    finally:
        if previous is None:
            os.environ.pop(PROMPT_VARIANT_ENV, None)
        else:
            os.environ[PROMPT_VARIANT_ENV] = previous

    best, reason = _select(results, max_final_issues)
    report = TuningReport(
        provider=provider_name,
        retriever_backend=retriever_backend,
        max_final_issues=max_final_issues,
        results=results,
        best=best,
        reason=reason,
        out_dir=out_dir,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "tuning.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "tuning.md").write_text(report.render_markdown(), encoding="utf-8")
    return report
