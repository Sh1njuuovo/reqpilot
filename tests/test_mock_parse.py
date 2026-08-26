from reqpilot.providers.mock import MockProvider


def test_parse_extracts_core_groups():
    provider = MockProvider()
    text = (
        "目前公司报销流程依赖纸质单据，效率低。系统面向报销员工与财务审核员。"
        "作为报销员工，我想要在线提交报销单，并查看审批进度。"
        "权限：管理员可查看全部单据，员工只能查看自己的单据。"
        "字段包括单据编号、员工姓名、金额、费用类型、提交日期、审批状态，必填项为单据编号、金额、提交日期。"
        "约束：必须支持幂等提交，防止重复报销；金额必须精确到分。"
        "异常：提交失败自动重试并提示；审批超时转人工处理。"
        "验收标准：员工提交后能查到进度，重复点击提交不会生成重复单据。"
    )
    parsed = provider.parse(text, "approval")
    assert parsed.background and "目前" in parsed.background
    assert parsed.target_users and "报销员工" in "".join(parsed.target_users)
    assert parsed.user_stories
    assert parsed.functional_requirements
    assert parsed.constraints and any("幂等" in c for c in parsed.constraints)
    assert parsed.permissions
    assert parsed.exception_flows
    assert parsed.acceptance_criteria


def test_parse_extracts_standalone_amount_field():
    provider = MockProvider()
    parsed = provider.parse("字段包括申请编号、金额、状态、日期。", "generic")
    names = [f.name for f in parsed.data_fields]
    assert "申请编号" in names
    assert "金额" in names
    amount = next(f for f in parsed.data_fields if f.name == "金额")
    assert amount.type == "number"


def test_parse_empty_text_produces_empty_groups():
    parsed = MockProvider().parse("你好", "generic")
    assert parsed.functional_requirements == []
    assert parsed.permissions == []
