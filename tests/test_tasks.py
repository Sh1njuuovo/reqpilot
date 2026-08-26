from reqpilot.models import DataEntity, DataField, FunctionalRequirement, PRDDocument
from reqpilot.tasks import export_csv, export_json, export_markdown, split_tasks


def _prd() -> PRDDocument:
    return PRDDocument(
        title="T",
        data_model=[DataEntity(name="单据", fields=[DataField(name="金额", type="number")])],
        functional_requirements=[
            FunctionalRequirement(id="FR-1", title="提交申请", description="支持提交申请并校验"),
        ],
    )


def test_split_tasks_has_dependencies():
    tasks = split_tasks(_prd())
    types = [t.type for t in tasks]
    assert "database" in types
    assert "backend" in types
    assert "frontend" in types
    assert "test" in types
    backend = next(t for t in tasks if t.type == "backend")
    frontend = next(t for t in tasks if t.type == "frontend")
    test = next(t for t in tasks if t.type == "test")
    assert backend.id in frontend.dependencies
    assert {backend.id, frontend.id} <= set(test.dependencies)


def test_exports_are_nonempty():
    tasks = split_tasks(_prd())
    assert "研发任务清单" in export_markdown(tasks)
    assert export_csv(tasks).startswith("id,type")
    data = export_json(tasks)
    assert '"type": "backend"' in data
