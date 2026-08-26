"""Development task splitting and export."""

from __future__ import annotations

import csv
import io
import json

from reqpilot.models import DevelopmentTask, Effort, PRDDocument


def _effort(description: str, fields: int) -> Effort:
    if len(description) > 60 or fields > 6:
        return "L"
    if len(description) > 24 or fields > 2:
        return "M"
    return "S"


def split_tasks(prd: PRDDocument) -> list[DevelopmentTask]:
    tasks: list[DevelopmentTask] = []

    if prd.data_model:
        entity_names = "、".join(e.name for e in prd.data_model)
        tasks.append(
            DevelopmentTask(
                id="T-001",
                type="database",
                title="核心数据表设计与索引",
                description=f"根据数据模型建立 {entity_names} 相关数据表、字段约束与查询索引。",
                acceptance_criteria=["表结构覆盖数据模型中全部字段", "关键查询字段建立索引"],
                effort=_effort(entity_names, sum(len(e.fields) for e in prd.data_model)),
                prd_refs=[e.name for e in prd.data_model],
            )
        )

    counter = 1
    for fr in prd.functional_requirements:
        counter += 1
        backend_id = f"T-{counter:03d}"
        tasks.append(
            DevelopmentTask(
                id=backend_id,
                type="backend",
                title=f"{fr.title}：后端接口",
                description=f"实现 {fr.title} 对应的接口、校验与权限控制。",
                dependencies=[t.id for t in tasks if t.type == "database"],
                acceptance_criteria=[f"{fr.id} 描述的能力可经 API 调用验证"],
                effort=_effort(fr.description, len(prd.data_model)),
                prd_refs=[fr.id],
            )
        )
        counter += 1
        frontend_id = f"T-{counter:03d}"
        tasks.append(
            DevelopmentTask(
                id=frontend_id,
                type="frontend",
                title=f"{fr.title}：页面实现",
                description=f"实现 {fr.title} 页面及多状态展示。",
                dependencies=[backend_id],
                acceptance_criteria=["页面与原型信息架构一致", "空/错误状态可见"],
                effort=_effort(fr.description, 0),
                prd_refs=[fr.id],
            )
        )
        counter += 1
        test_id = f"T-{counter:03d}"
        tasks.append(
            DevelopmentTask(
                id=test_id,
                type="test",
                title=f"{fr.title}：测试用例",
                description=f"为 {fr.title} 编写功能、边界与异常用例。",
                dependencies=[backend_id, frontend_id],
                acceptance_criteria=["覆盖正常路径与异常路径", "用例通过率达到验收标准"],
                effort=_effort(fr.description, 0),
                prd_refs=[fr.id],
            )
        )
    return tasks


def export_markdown(tasks: list[DevelopmentTask]) -> str:
    lines = ["# 研发任务清单", "", "| ID | 类型 | 标题 | 工作量 | 依赖 |", "| --- | --- | --- | --- | --- |"]
    for t in tasks:
        deps = ",".join(t.dependencies) or "-"
        lines.append(f"| {t.id} | {t.type} | {t.title} | {t.effort} | {deps} |")
    for t in tasks:
        lines += ["", f"### {t.id} {t.title}", "", t.description, ""]
        if t.acceptance_criteria:
            lines += ["验收标准："] + [f"- {c}" for c in t.acceptance_criteria] + [""]
    return "\n".join(lines)


def export_csv(tasks: list[DevelopmentTask]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "type", "title", "description", "dependencies", "effort", "acceptance_criteria", "prd_refs"])
    for t in tasks:
        writer.writerow(
            [
                t.id,
                t.type,
                t.title,
                t.description,
                ";".join(t.dependencies),
                t.effort,
                ";".join(t.acceptance_criteria),
                ";".join(t.prd_refs),
            ]
        )
    return buf.getvalue()


def export_json(tasks: list[DevelopmentTask]) -> str:
    return json.dumps([t.model_dump() for t in tasks], ensure_ascii=False, indent=2)
