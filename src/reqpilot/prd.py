"""Structured-PRD helpers: markdown rendering."""

from __future__ import annotations

from reqpilot.models import PRDDocument


def render_markdown(prd: PRDDocument) -> str:
    lines: list[str] = [f"# {prd.title}", ""]
    if prd.summary:
        lines += [prd.summary, ""]
    if prd.background:
        lines += ["## 背景", "", prd.background, ""]
    if prd.target_users:
        lines += ["## 目标用户", ""]
        lines += [f"- {u}" for u in prd.target_users] + [""]
    if prd.functional_requirements:
        lines += ["## 功能需求", ""]
        for fr in prd.functional_requirements:
            lines += [f"### {fr.id} {fr.title}（{fr.priority}）", "", fr.description, ""]
    if prd.permissions:
        lines += ["## 权限", ""] + [f"- {p}" for p in prd.permissions] + [""]
    if prd.non_functional:
        lines += ["## 非功能约束", ""] + [f"- {c}" for c in prd.non_functional] + [""]
    if prd.data_model:
        lines += ["## 数据模型", ""]
        for entity in prd.data_model:
            lines.append(f"### {entity.name}")
            lines.append("")
            lines.append("| 字段 | 类型 | 必填 |")
            lines.append("| --- | --- | --- |")
            for f in entity.fields:
                lines.append(f"| {f.name} | {f.type} | {'是' if f.required else '否'} |")
            lines.append("")
    if prd.pages:
        lines += ["## 页面信息架构", ""]
        for page in prd.pages:
            states = "、".join(page.states)
            lines.append(f"- **{page.title}**（{page.id}）：状态 [{states}]；组件：{'、'.join(page.components)}")
        lines.append("")
    if prd.acceptance_criteria:
        lines += ["## 验收标准", ""] + [f"- {c}" for c in prd.acceptance_criteria] + [""]
    if prd.open_questions:
        lines += ["## 待确认问题", ""] + [f"- {q}" for q in prd.open_questions] + [""]
    return "\n".join(lines)
