from reqpilot.models import AgentRun, DataField, ParsedRequirement, RequirementInput, ReviewIssue


def test_requirement_input_min_length():
    try:
        RequirementInput(text="")
        raise AssertionError("empty text should be rejected")
    except ValueError:
        pass


def test_parsed_requirement_defaults():
    parsed = ParsedRequirement()
    assert parsed.target_users == []
    assert parsed.functional_requirements == []
    assert parsed.acceptance_criteria == []


def test_data_field_validation():
    f = DataField(name="金额", type="number", required=True)
    assert f.type == "number"


def test_review_issue_roles_default():
    issue = ReviewIssue(role="product", category="completeness", severity="major", title="x")
    assert issue.roles == []
    assert issue.id == ""


def test_agent_run_digest_stable():
    assert AgentRun.digest("abc") == AgentRun.digest("abc")
    assert AgentRun.digest("abc") != AgentRun.digest("abd")


def test_agent_run_defaults():
    run = AgentRun()
    assert run.status == "running"
    assert len(run.id) == 12
