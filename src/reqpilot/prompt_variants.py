"""Review-prompt variants that can be measured against the golden set.

Prompt wording is normally tuned by hand and the result is not reproducible. This
module keeps the wording in named variants so the evaluation harness can measure
each one on the same 12 cases and pick a winner by a stated rule.
"""

from __future__ import annotations

BASELINE = """只输出最重要的、确有依据的问题：同类问题合并为一条，每个角色最多 5 条，宁缺毋滥，避免泛泛而谈。
输出 JSON 对象：{"issues": [{"category": "interaction|logic|permission|data|completeness|consistency", "severity": "critical|major|minor|suggestion", "title": "简短标题", "description": "问题说明", "evidence": ["依据原文"], "suggestion": "修复建议"}]}
"""

EVIDENCE_FIRST = """每条问题都必须能在原文里找到出处，evidence 至少给一句原文片段，找不到出处的不要输出。
同类问题合并为一条，每个角色最多 5 条，宁可少报也不要臆测。
输出 JSON 对象：{"issues": [{"category": "interaction|logic|permission|data|completeness|consistency", "severity": "critical|major|minor|suggestion", "title": "简短标题", "description": "问题说明", "evidence": ["依据原文"], "suggestion": "修复建议"}]}
"""

COVERAGE_FIRST = """先覆盖所有你能判断的类别，再按严重程度排序，每个角色最多 8 条，同类问题合并为一条。
不要求每条都给出原文片段，但描述里要写清楚是哪个需求点存在问题。
输出 JSON 对象：{"issues": [{"category": "interaction|logic|permission|data|completeness|consistency", "severity": "critical|major|minor|suggestion", "title": "简短标题", "description": "问题说明", "evidence": ["依据原文"], "suggestion": "修复建议"}]}
"""

REVIEW_PROMPT_VARIANTS: dict[str, str] = {
    "baseline": BASELINE,
    "evidence_first": EVIDENCE_FIRST,
    "coverage_first": COVERAGE_FIRST,
}

DEFAULT_VARIANT = "baseline"


def resolve_variant(name: str | None) -> str:
    """Return a usable variant name, falling back to the default."""

    if name and name in REVIEW_PROMPT_VARIANTS:
        return name
    return DEFAULT_VARIANT


def variant_prompt(name: str | None) -> str:
    """Return the review prompt text for a variant name."""

    return REVIEW_PROMPT_VARIANTS[resolve_variant(name)]
