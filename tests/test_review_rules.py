from reqpilot.providers.mock import MockProvider


def _parse(text):
    return MockProvider().parse(text, "generic")


def test_product_flags_missing_acceptance():
    parsed = _parse("系统面向内部用户，支持查询列表。")
    issues = MockProvider().review("product", parsed, "系统面向内部用户，支持查询列表。")
    titles = [i.title for i in issues]
    assert "缺少验收标准" in titles
    assert "缺少目标用户定义" not in titles


def test_backend_flags_missing_permission_model():
    text = "系统支持审批提交。字段包括申请编号、金额。"
    parsed = _parse(text)
    issues = MockProvider().review("backend", parsed, text)
    assert any(i.category == "permission" for i in issues)


def test_backend_flags_missing_idempotency():
    text = "系统支持创建申请并提交。字段包括申请编号、金额。"
    parsed = _parse(text)
    issues = MockProvider().review("backend", parsed, text)
    assert any(i.title == "写操作缺少幂等性设计" for i in issues)


def test_frontend_flags_form_validation():
    text = "系统支持在表单中填写报销申请并提交。"
    parsed = _parse(text)
    issues = MockProvider().review("frontend", parsed, text)
    assert any(i.category == "interaction" and i.severity == "major" for i in issues)


def test_test_flags_missing_exception_paths():
    text = "系统支持批量导入数据与导出报表。"
    parsed = _parse(text)
    issues = MockProvider().review("test", parsed, text)
    assert any(i.title == "缺少异常与边界用例" for i in issues)


def test_review_roles_are_typed():
    text = "系统支持查询列表。"
    parsed = _parse(text)
    for role in ("product", "frontend", "backend", "test"):
        issues = MockProvider().review(role, parsed, text)
        assert all(i.role == role for i in issues)
