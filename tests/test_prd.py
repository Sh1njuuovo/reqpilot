from reqpilot.models import ParsedRequirement
from reqpilot.prd import render_markdown
from reqpilot.providers.mock import MockProvider


def test_prd_generation_pages_match_functional_requirements():
    text = "系统面向内部用户，支持查询审批记录列表。系统支持导出明细报表。"
    parsed = MockProvider().parse(text, "approval")
    prd = MockProvider().generate_prd(parsed, "approval", text)
    assert len(prd.functional_requirements) >= 2
    assert len(prd.pages) == len(prd.functional_requirements)
    assert prd.pages[0].id == "page-1"
    assert prd.pages[0].states


def test_prd_markdown_contains_sections():
    parsed = ParsedRequirement(
        background="背景",
        target_users=["用户"],
        functional_requirements=["支持查询列表"],
        acceptance_criteria=["验收通过"],
    )
    prd = MockProvider().generate_prd(parsed, "generic", "支持查询列表")
    md = render_markdown(prd)
    assert "## 功能需求" in md
    assert "## 验收标准" in md
    assert "支持查询列表" in md
