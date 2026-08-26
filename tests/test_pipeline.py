import pytest

from reqpilot.config import Settings
from reqpilot.models import AgentRun, RequirementInput
from reqpilot.pipeline import SAMPLE_REQUIREMENT, PipelineBuilder, PipelineState, run_pipeline
from reqpilot.providers.base import ProviderError
from reqpilot.providers.mock import MockProvider


def test_pipeline_end_to_end_mock():
    result = run_pipeline(SAMPLE_REQUIREMENT, domain="approval", provider_name="mock")
    assert result.run.status == "succeeded"
    assert result.prd is not None
    assert result.issues
    assert result.tasks
    assert result.prototype_html
    assert result.run.fingerprint
    assert result.run.citations


def test_pipeline_deterministic_fingerprint():
    a = run_pipeline(SAMPLE_REQUIREMENT, provider_name="mock")
    b = run_pipeline(SAMPLE_REQUIREMENT, provider_name="mock")
    assert a.run.fingerprint == b.run.fingerprint
    assert a.run.id != b.run.id


def test_pipeline_llm_without_key_raises():
    settings = Settings(llm_api_key=None)
    with pytest.raises(ProviderError):
        run_pipeline(SAMPLE_REQUIREMENT, provider_name="llm", settings=settings)


def test_pipeline_human_confirm_interrupts():
    result = run_pipeline(SAMPLE_REQUIREMENT, provider_name="mock", human_confirm=True)
    assert result.run.status == "needs_confirmation"
    assert result.tasks == []


class FailingProvider:
    name = "failing"

    def parse(self, text, domain):
        return MockProvider().parse(text, domain)

    def review(self, role, parsed, context):
        raise ProviderError("review boom")

    def generate_prd(self, parsed, domain, context):
        return MockProvider().generate_prd(parsed, domain, context)


def test_review_failure_records_error_without_fallback():
    builder = PipelineBuilder(FailingProvider())
    graph = builder.build()
    initial: PipelineState = {
        "run": AgentRun(),
        "input": RequirementInput(text=SAMPLE_REQUIREMENT, domain="approval"),
        "knowledge": [],
        "raw_issue_parts": [],
        "issues": [],
        "issues_removed": 0,
        "step_traces": [],
        "errors": [],
        "fallbacks": [],
        "raw_issue_count": 0,
    }
    final = graph.invoke(initial)
    assert final["run"].status == "failed"
    assert any(t.step.startswith("review") and not t.ok for t in final["step_traces"])
    assert any("review:" in e for e in final["errors"])
    assert final["issues"] == []
