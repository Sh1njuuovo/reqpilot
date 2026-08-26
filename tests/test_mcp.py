import json

from reqpilot.mcp_server import analyze_requirement, export_tasks


def test_mcp_analyze_requirement():
    out = analyze_requirement(
        "系统面向客服人员，支持创建工单并提交。权限：客服只能查看自己的工单。"
        "字段包括工单编号、状态。验收标准：创建后可见。",
        provider="mock",
    )
    data = json.loads(out)
    assert data["status"] == "succeeded"
    assert data["prd_title"]
    assert data["issue_count"] > 0
    assert data["task_count"] > 0


def test_mcp_export_tasks():
    tasks = export_tasks(
        "系统支持导出报表。字段包括报表编号、日期。验收标准：导出成功。",
        provider="mock",
    )
    assert "研发任务清单" in tasks
    assert "| T-" in tasks
