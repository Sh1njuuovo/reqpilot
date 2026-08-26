"""Run the pipeline over eval/cases and produce measured metrics."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from reqpilot.config import project_root
from reqpilot.pipeline import run_pipeline


@dataclass
class Case:
    id: str
    title: str
    text: str
    domain: str
    required_groups: list[str]
    golden_issues: list[tuple[str, str]]


@dataclass
class CaseResult:
    case_id: str
    title: str
    success: bool
    completeness: float
    issue_recall: float
    issue_precision: float
    dedup_rate: float
    duration_ms: int
    produced: list[tuple[str, str]] = field(default_factory=list)
    golden: list[tuple[str, str]] = field(default_factory=list)
    raw_issue_count: int = 0
    final_issue_count: int = 0
    issue_details: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "case_id": self.case_id,
            "title": self.title,
            "success": self.success,
            "completeness": round(self.completeness, 4),
            "issue_recall": round(self.issue_recall, 4),
            "issue_precision": round(self.issue_precision, 4),
            "dedup_rate": round(self.dedup_rate, 4),
            "duration_ms": self.duration_ms,
            "produced": [list(p) for p in sorted(self.produced)],
            "golden": [list(g) for g in sorted(self.golden)],
            "raw_issue_count": self.raw_issue_count,
            "final_issue_count": self.final_issue_count,
            "issue_details": self.issue_details,
        }


@dataclass
class EvalSummary:
    provider: str
    out_dir: Path
    cases: list[CaseResult]
    aggregate: dict

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "aggregate": {
                k: round(v, 4) if isinstance(v, float) else v for k, v in self.aggregate.items()
            },
            "cases": [c.to_dict() for c in self.cases],
        }

    def render_markdown(self) -> str:
        a = self.aggregate
        lines = [
            f"# ReqPilot Evaluation — provider `{self.provider}`",
            "",
            f"- 生成时间：{datetime.now(UTC).isoformat(timespec='seconds')}",
            f"- 用例数：{len(self.cases)}",
            f"- 管线成功率：{a['success_rate']:.2%}",
            f"- 平均字段完整性：{a['avg_completeness']:.2%}",
            f"- 平均问题召回：{a['avg_recall']:.2%}",
            f"- 平均问题精确率：{a['avg_precision']:.2%}",
            f"- 平均去重率：{a['avg_dedup_rate']:.2%}",
            f"- 平均耗时：{a['avg_duration_ms']:.0f} ms",
            "",
            "| Case | 成功 | 完整性 | 召回 | 精确率 | 去重率 | 耗时(ms) |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for c in self.cases:
            lines.append(
                f"| {c.case_id} | {'✓' if c.success else '✗'} | {c.completeness:.0%} | "
                f"{c.issue_recall:.0%} | {c.issue_precision:.0%} | {c.dedup_rate:.0%} | {c.duration_ms} |"
            )
        return "\n".join(lines)


def load_cases(cases_dir: str | Path) -> list[Case]:
    p = Path(cases_dir)
    cases: list[Case] = []
    for path in sorted(p.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        golden = data.get("golden", {})
        cases.append(
            Case(
                id=data["id"],
                title=data["title"],
                text=data["input"]["text"],
                domain=data["input"].get("domain", "generic"),
                required_groups=golden.get("required_groups", []),
                golden_issues=[(i["role"], i["category"]) for i in golden.get("issues", [])],
            )
        )
    return cases


def evaluate_one(case: Case, provider_name: str, retriever_backend: str = "keyword") -> CaseResult:
    result = run_pipeline(
        case.text,
        domain=case.domain,
        provider_name=provider_name,
        retriever_backend=retriever_backend,
    )
    duration = (
        int((result.run.completed_at - result.run.created_at).total_seconds() * 1000)
        if result.run.completed_at
        else 0
    )
    parsed = result.parsed
    filled = 0
    for group in case.required_groups:
        value = getattr(parsed, group, None) if parsed else None
        if isinstance(value, list) and value or value:
            filled += 1
    completeness = filled / len(case.required_groups) if case.required_groups else 1.0

    produced: set[tuple[str, str]] = set()
    for issue in result.issues:
        for role in (issue.roles or [issue.role]):
            produced.add((role, issue.category))
    golden_set = set(case.golden_issues)
    matched = len(golden_set & produced)
    recall = matched / len(golden_set) if golden_set else 1.0
    precision = matched / len(produced) if produced else (1.0 if not golden_set else 0.0)
    raw = result.raw_issue_count
    dedup_rate = (raw - len(result.issues)) / raw if raw > 0 else 0.0
    return CaseResult(
        case_id=case.id,
        title=case.title,
        success=result.run.status == "succeeded",
        completeness=completeness,
        issue_recall=recall,
        issue_precision=precision,
        dedup_rate=dedup_rate,
        duration_ms=duration,
        produced=sorted(produced),
        golden=sorted(case.golden_issues),
        raw_issue_count=raw,
        final_issue_count=len(result.issues),
        issue_details=[
            {
                "role": i.role,
                "category": i.category,
                "severity": i.severity,
                "title": i.title,
            }
            for i in result.issues
        ],
    )


def run_eval(
    provider_name: str = "llm",
    retriever_backend: str = "keyword",
    cases_dir: str | Path | None = None,
    out_dir: str | Path | None = None,
) -> EvalSummary:
    root = project_root()
    cases_dir = Path(cases_dir or (root / "eval" / "cases"))
    out_dir = Path(out_dir or (root / "reports" / "eval"))
    cases = load_cases(cases_dir)
    results = [evaluate_one(c, provider_name, retriever_backend) for c in cases]
    n = len(results)
    aggregate = {
        "success_rate": sum(1 for r in results if r.success) / n,
        "avg_completeness": sum(r.completeness for r in results) / n,
        "avg_recall": sum(r.issue_recall for r in results) / n,
        "avg_precision": sum(r.issue_precision for r in results) / n,
        "avg_dedup_rate": sum(r.dedup_rate for r in results) / n,
        "avg_duration_ms": sum(r.duration_ms for r in results) / n,
        "total_duration_ms": sum(r.duration_ms for r in results),
    }
    summary = EvalSummary(provider=provider_name, out_dir=out_dir, cases=results, aggregate=aggregate)
    summary.aggregate["retriever_backend"] = retriever_backend
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    stem = f"eval_{provider_name}_{retriever_backend}"
    (out_dir / f"{stem}_{ts}.json").write_text(
        json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / f"{stem}_{ts}.md").write_text(
        summary.render_markdown(), encoding="utf-8"
    )
    (out_dir / f"{stem}_latest.json").write_text(
        json.dumps(summary.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / f"{stem}_latest.md").write_text(
        summary.render_markdown(), encoding="utf-8"
    )
    return summary
