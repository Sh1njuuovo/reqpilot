"""MCP stdio server exposing ReqPilot tools to external agents (mcp 2.x)."""

from __future__ import annotations

import json

from mcp.server import MCPServer

from reqpilot.pipeline import run_pipeline

server = MCPServer(
    name="reqpilot",
    description="Requirements engineering agent: natural language in, PRD + multi-role review + dev tasks out.",
)


@server.tool()
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


@server.tool()
def export_tasks(text: str, domain: str = "generic", provider: str = "mock") -> str:
    """Run the pipeline and return development tasks as Markdown."""

    result = run_pipeline(text, domain=domain, provider_name=provider)
    return result.tasks_markdown


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
