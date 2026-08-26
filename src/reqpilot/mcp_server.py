"""MCP stdio server exposing ReqPilot tools to external agents."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from reqpilot.pipeline import run_pipeline

mcp = FastMCP("reqpilot")


@mcp.tool()
def analyze_requirement(text: str, domain: str = "generic") -> str:
    """Run the ReqPilot pipeline and return a JSON summary of PRD, issues, and tasks."""

    result = run_pipeline(text, domain=domain, provider_name="mock")
    return json.dumps(
        {
            "run_id": result.run.id,
            "status": result.run.status,
            "prd_title": result.prd.title if result.prd else None,
            "issue_count": len(result.issues),
            "issues": [i.model_dump() for i in result.issues],
            "task_count": len(result.tasks),
        },
        ensure_ascii=False,
    )


@mcp.tool()
def export_tasks(text: str, domain: str = "generic", provider: str = "mock") -> str:
    """Run the pipeline and return development tasks as Markdown."""

    result = run_pipeline(text, domain=domain, provider_name=provider)
    return result.tasks_markdown


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
