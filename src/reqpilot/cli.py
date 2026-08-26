"""Command-line interface: smoke / demo / serve / eval."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from reqpilot.config import project_root
from reqpilot.pipeline import SAMPLE_DOMAIN, SAMPLE_REQUIREMENT, PipelineResult, run_pipeline


def _summary(result: PipelineResult) -> dict:
    issues = result.issues
    by_severity: dict[str, int] = {}
    by_role: dict[str, int] = {}
    for i in issues:
        by_severity[i.severity] = by_severity.get(i.severity, 0) + 1
        by_role[i.role] = by_role.get(i.role, 0) + 1
    tasks = result.tasks
    by_type: dict[str, int] = {}
    for t in tasks:
        by_type[t.type] = by_type.get(t.type, 0) + 1
    duration = (
        int((result.run.completed_at - result.run.created_at).total_seconds() * 1000)
        if result.run.completed_at
        else 0
    )
    return {
        "run_id": result.run.id,
        "provider": result.run.provider,
        "status": result.run.status,
        "duration_ms": duration,
        "input_hash": result.run.input_text_hash,
        "fingerprint": result.run.fingerprint,
        "citations": len(result.citations),
        "parsed": {
            "functional_requirements": len(result.parsed.functional_requirements) if result.parsed else 0,
            "permissions": len(result.parsed.permissions) if result.parsed else 0,
            "data_fields": len(result.parsed.data_fields) if result.parsed else 0,
            "constraints": len(result.parsed.constraints) if result.parsed else 0,
            "exception_flows": len(result.parsed.exception_flows) if result.parsed else 0,
            "acceptance_criteria": len(result.parsed.acceptance_criteria) if result.parsed else 0,
        },
        "issues": {
            "total": len(issues),
            "raw": result.raw_issue_count,
            "dedup_removed": result.raw_issue_count - len(issues),
            "by_severity": by_severity,
            "by_role": by_role,
        },
        "prd": {
            "title": result.prd.title if result.prd else "",
            "pages": len(result.prd.pages) if result.prd else 0,
        },
        "tasks": {"total": len(tasks), "by_type": by_type},
        "fallbacks": len(result.run.fallbacks),
        "errors": result.run.errors,
    }


def _write_bundle(out_dir: Path, result: PipelineResult) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = _summary(result)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "run.json").write_text(result.run.model_dump_json(indent=2), encoding="utf-8")
    if result.parsed:
        (out_dir / "parsed.json").write_text(
            json.dumps(result.parsed.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if result.prd:
        (out_dir / "prd.json").write_text(
            json.dumps(result.prd.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
    (out_dir / "prd.md").write_text(result.prd_markdown or "", encoding="utf-8")
    (out_dir / "issues.json").write_text(
        json.dumps([i.model_dump() for i in result.issues], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "tasks.md").write_text(result.tasks_markdown or "", encoding="utf-8")
    (out_dir / "tasks.csv").write_text(result.tasks_csv or "", encoding="utf-8")
    (out_dir / "tasks.json").write_text(result.tasks_json or "[]", encoding="utf-8")
    (out_dir / "prototype.html").write_text(result.prototype_html or "", encoding="utf-8")
    (out_dir / "citations.json").write_text(
        json.dumps([c.model_dump() for c in result.citations], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_dir / "summary.json"


def _print_summary(summary: dict) -> None:
    print(f"run_id       {summary['run_id']}")
    print(f"provider     {summary['provider']}")
    print(f"status       {summary['status']}  ({summary['duration_ms']} ms)")
    print(f"input hash   {summary['input_hash']}")
    print(f"fingerprint  {summary['fingerprint']}")
    print(f"citations    {summary['citations']}")
    print(f"parsed       {summary['parsed']}")
    print(f"issues       {summary['issues']}")
    print(f"prd          {summary['prd']}")
    print(f"tasks        {summary['tasks']}")
    print(f"fallbacks    {summary['fallbacks']}")
    if summary["errors"]:
        print("errors       " + " | ".join(summary["errors"]))


def cmd_smoke(args: argparse.Namespace) -> int:
    out = Path(args.out)
    result = run_pipeline(
        SAMPLE_REQUIREMENT,
        domain=SAMPLE_DOMAIN,
        provider_name=args.provider,
        retriever_backend=args.retriever,
    )
    summary = _summary(result)
    _print_summary(summary)
    path = _write_bundle(out, result)
    print(f"\nartifacts -> {path.parent}")
    if result.run.status != "succeeded" or not result.prd or not result.tasks:
        print("SMOKE FAILED", file=sys.stderr)
        return 1
    print("SMOKE OK")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    out = Path(args.out)
    result = run_pipeline(
        SAMPLE_REQUIREMENT,
        domain=SAMPLE_DOMAIN,
        provider_name=args.provider,
        retriever_backend=args.retriever,
    )
    path = _write_bundle(out, result)
    _print_summary(_summary(result))
    print(f"\ndemo bundle -> {path.parent}")
    print("demo steps:")
    print("  1. 打开 prototype.html 演示单文件多页面原型（表单校验/状态切换/深浅色）")
    print("  2. 对照 prd.md 讲结构化 PRD 与页面信息架构")
    print("  3. 对照 issues.json 讲多角色审查与去重合并")
    print("  4. 对照 tasks.md 讲任务拆分与依赖关系")
    if result.run.status != "succeeded":
        print("DEMO FAILED", file=sys.stderr)
        return 1
    print("DEMO OK")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    uvicorn.run("reqpilot.api:app", host=args.host, port=args.port, reload=False)
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from reqpilot.eval.runner import run_eval

    result = run_eval(
        provider_name=args.provider,
        retriever_backend=args.retriever,
        out_dir=Path(args.out),
    )
    print(result.render_markdown())
    print(f"\neval report -> {result.out_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reqpilot", description="ReqPilot requirements engineering agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_smoke = sub.add_parser("smoke", help="run the sample requirement end-to-end and assert success")
    p_smoke.add_argument("--out", default=str(project_root() / "reports" / "smoke"))
    p_smoke.add_argument("--provider", default="mock", choices=["mock", "llm"])
    p_smoke.add_argument("--retriever", default="keyword", choices=["keyword", "vector"])
    p_smoke.set_defaults(func=cmd_smoke)

    p_demo = sub.add_parser("demo", help="produce a demo bundle from the sample requirement")
    p_demo.add_argument("--out", default=str(project_root() / "reports" / "demo"))
    p_demo.add_argument("--provider", default="mock", choices=["mock", "llm"])
    p_demo.add_argument("--retriever", default="keyword", choices=["keyword", "vector"])
    p_demo.set_defaults(func=cmd_demo)

    p_serve = sub.add_parser("serve", help="start the FastAPI service")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    p_eval = sub.add_parser("eval", help="run the evaluation suite over eval/cases")
    p_eval.add_argument("--provider", default="mock", choices=["mock", "llm"])
    p_eval.add_argument("--retriever", default="keyword", choices=["keyword", "vector"])
    p_eval.add_argument("--out", default=str(project_root() / "reports" / "eval"))
    p_eval.set_defaults(func=cmd_eval)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    start = time.monotonic()
    code = args.func(args)
    print(f"total {int((time.monotonic() - start) * 1000)} ms")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
