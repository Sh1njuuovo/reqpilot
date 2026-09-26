"""Command-line interface: smoke / demo / agent / serve / eval."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from reqpilot.agent import (
    REVIEW_FIX_GOAL,
    AgentLoop,
    WorkspaceSandbox,
    review_fix_verifier,
)
from reqpilot.config import project_root
from reqpilot.pipeline import SAMPLE_DOMAIN, SAMPLE_REQUIREMENT, PipelineResult, run_pipeline
from reqpilot.providers import ProviderError


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
    (out_dir / "requirement.md").write_text(result.input_text or "", encoding="utf-8")
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
    try:
        result = run_pipeline(
            SAMPLE_REQUIREMENT,
            domain=SAMPLE_DOMAIN,
            provider_name=args.provider,
            retriever_backend=args.retriever,
        )
    except ProviderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
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
    try:
        result = run_pipeline(
            SAMPLE_REQUIREMENT,
            domain=SAMPLE_DOMAIN,
            provider_name=args.provider,
            retriever_backend=args.retriever,
        )
    except ProviderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
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


def cmd_agent(args: argparse.Namespace) -> int:
    from reqpilot.config import Settings
    from reqpilot.providers import get_provider

    workspace = Path(args.workspace).expanduser()
    if not workspace.is_dir():
        print(f"ERROR: 工作区不存在: {workspace}", file=sys.stderr)
        return 1
    if not (workspace / "issues.json").exists():
        print(
            f"ERROR: 工作区缺少 issues.json，请先运行 reqpilot demo --out {workspace}",
            file=sys.stderr,
        )
        return 1
    try:
        provider = get_provider(args.provider, Settings.from_env())
    except ProviderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    sandbox = WorkspaceSandbox(workspace)
    goal_text = args.goal or REVIEW_FIX_GOAL
    loop = AgentLoop(
        provider,
        sandbox,
        goal_text,
        max_steps=args.max_steps,
        verifier=review_fix_verifier(sandbox),
    )
    result = loop.run()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "agent-run.json").write_text(
        result.run.model_dump_json(indent=2), encoding="utf-8"
    )
    (out_dir / "agent-transcript.json").write_text(
        json.dumps(result.transcript, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tool_counts: dict[str, int] = {}
    for trace in result.run.tool_calls:
        tool_counts[trace.tool] = tool_counts.get(trace.tool, 0) + 1
    summary = {
        "run_id": result.run.id,
        "provider": result.run.provider,
        "goal": result.goal.text,
        "status": result.goal.status,
        "steps_used": result.goal.steps_used,
        "max_steps": result.goal.max_steps,
        "completion_claimed": result.goal.completion_claimed,
        "completion_verified": result.goal.completion_verified,
        "checks": result.goal.checks,
        "tool_calls": tool_counts,
        "fallbacks": result.run.fallbacks,
        "errors": result.run.errors,
        "fingerprint": result.run.fingerprint,
        "workspace": str(sandbox.root),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"run_id       {summary['run_id']}")
    print(f"goal         {summary['goal']}")
    print(f"status       {summary['status']}  (steps {summary['steps_used']}/{summary['max_steps']})")
    print(f"claimed      {summary['completion_claimed']}")
    print(f"verified     {summary['completion_verified']}")
    print(f"tool calls   {summary['tool_calls']}")
    for check in result.goal.checks:
        print(f"  - {check}")
    if result.run.fallbacks:
        print("fallbacks    " + " | ".join(result.run.fallbacks))
    if result.run.errors:
        print("errors       " + " | ".join(result.run.errors))
    print(f"\nartifacts -> {out_dir}")
    if not result.goal.completion_verified:
        print("AGENT GOAL NOT VERIFIED", file=sys.stderr)
        return 1
    print("AGENT OK")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from reqpilot.eval.runner import run_eval

    try:
        result = run_eval(
            provider_name=args.provider,
            retriever_backend=args.retriever,
            out_dir=Path(args.out),
        )
    except ProviderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(result.render_markdown())
    print(f"\neval report -> {result.out_dir}")
    return 0


def cmd_tune(args: argparse.Namespace) -> int:
    from reqpilot.tuning import tune_review_prompt

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    try:
        report = tune_review_prompt(
            provider_name=args.provider,
            retriever_backend=args.retriever,
            variants=variants,
            out_dir=Path(args.out),
            max_final_issues=args.max_final_issues,
        )
    except ProviderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(report.render_markdown())
    print(f"\ntuning report -> {report.out_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="reqpilot", description="ReqPilot requirements engineering agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_smoke = sub.add_parser("smoke", help="run the sample requirement end-to-end and assert success")
    p_smoke.add_argument("--out", default=str(project_root() / "reports" / "smoke"))
    p_smoke.add_argument("--provider", default="llm", choices=["llm"])
    p_smoke.add_argument("--retriever", default="keyword", choices=["keyword", "vector"])
    p_smoke.set_defaults(func=cmd_smoke)

    p_demo = sub.add_parser("demo", help="produce a demo bundle from the sample requirement")
    p_demo.add_argument("--out", default=str(project_root() / "reports" / "demo"))
    p_demo.add_argument("--provider", default="llm", choices=["llm"])
    p_demo.add_argument("--retriever", default="keyword", choices=["keyword", "vector"])
    p_demo.set_defaults(func=cmd_demo)

    p_agent = sub.add_parser(
        "agent", help="run the sandboxed tool-calling agent over a demo workspace"
    )
    p_agent.add_argument("--workspace", default=str(project_root() / "reports" / "demo"))
    p_agent.add_argument("--goal", default="", help="自定义目标；默认处理评审里的阻塞问题")
    p_agent.add_argument("--max-steps", type=int, default=8)
    p_agent.add_argument("--provider", default="llm", choices=["llm"])
    p_agent.add_argument("--out", default=str(project_root() / "reports" / "agent"))
    p_agent.set_defaults(func=cmd_agent)

    p_serve = sub.add_parser("serve", help="start the FastAPI service")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=cmd_serve)

    p_eval = sub.add_parser("eval", help="run the evaluation suite over eval/cases")
    p_eval.add_argument("--provider", default="llm", choices=["llm"])
    p_eval.add_argument("--retriever", default="keyword", choices=["keyword", "vector"])
    p_eval.add_argument("--out", default=str(project_root() / "reports" / "eval"))
    p_eval.set_defaults(func=cmd_eval)

    p_tune = sub.add_parser(
        "tune", help="measure review-prompt variants on the golden set and pick one"
    )
    p_tune.add_argument(
        "--variants", default="baseline,evidence_first,coverage_first", help="逗号分隔的变体名"
    )
    p_tune.add_argument("--provider", default="llm", choices=["llm"])
    p_tune.add_argument("--retriever", default="keyword", choices=["keyword", "vector"])
    p_tune.add_argument("--max-final-issues", type=int, default=20)
    p_tune.add_argument("--out", default=str(project_root() / "reports" / "tuning"))
    p_tune.set_defaults(func=cmd_tune)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    start = time.monotonic()
    code = args.func(args)
    print(f"total {int((time.monotonic() - start) * 1000)} ms")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
