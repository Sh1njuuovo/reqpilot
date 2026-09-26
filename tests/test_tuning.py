import json

import pytest

from reqpilot.config import Settings
from reqpilot.prompt_variants import REVIEW_PROMPT_VARIANTS, resolve_variant, variant_prompt
from reqpilot.providers.llm import OpenAICompatibleProvider
from reqpilot.tuning import PROMPT_VARIANT_ENV, tune_review_prompt


class _Case:
    def __init__(self, final_issue_count):
        self.final_issue_count = final_issue_count


class _Summary:
    def __init__(self, aggregate, case_count=12, final_issues=8):
        self.aggregate = aggregate
        self.cases = [_Case(final_issues)] * case_count


def _aggregate(recall, precision=0.19, dedup=0.013, duration=18000.0, success=1.0):
    return {
        "success_rate": success,
        "avg_recall": recall,
        "avg_precision": precision,
        "avg_dedup_rate": dedup,
        "avg_duration_ms": duration,
    }


def test_variants_are_named_and_resolvable():
    assert "baseline" in REVIEW_PROMPT_VARIANTS
    assert len(REVIEW_PROMPT_VARIANTS) >= 3
    assert resolve_variant("evidence_first") == "evidence_first"
    assert resolve_variant("does-not-exist") == "baseline"
    assert variant_prompt(None) == REVIEW_PROMPT_VARIANTS["baseline"]


def test_prompt_variant_reaches_the_model(monkeypatch):
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"choices": [{"message": {"content": '{"issues": []}'}}]}

        def raise_for_status(self):
            return None

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return FakeResponse()

    monkeypatch.setattr("reqpilot.providers.llm.httpx.post", fake_post)
    provider = OpenAICompatibleProvider(
        Settings(llm_api_key="sk-test", prompt_variant="evidence_first")
    )
    provider.review("product", __import__("reqpilot.models", fromlist=["ParsedRequirement"]).ParsedRequirement(), "需求")

    system = captured["payload"]["messages"][0]["content"]
    assert "找不到出处的不要输出" in system


def test_tuning_picks_the_highest_recall_eligible_variant(tmp_path, monkeypatch):
    measured = {
        "baseline": _Summary(_aggregate(0.865), final_issues=8),
        "evidence_first": _Summary(_aggregate(0.90), final_issues=12),
        "coverage_first": _Summary(_aggregate(0.95), final_issues=30),
    }

    def fake_run_eval(provider_name="llm", retriever_backend="keyword", cases_dir=None, out_dir=None):
        variant = out_dir.name
        return measured[variant]

    monkeypatch.setattr("reqpilot.tuning.run_eval", fake_run_eval)
    report = tune_review_prompt(out_dir=tmp_path)

    # coverage_first 召回最高但问题数超预算，只能选 evidence_first
    assert report.best == "evidence_first"
    assert "2/3" in report.reason
    assert sum(r.eligible for r in report.results) == 2
    assert (tmp_path / "tuning.json").exists()
    assert (tmp_path / "tuning.md").exists()
    payload = json.loads((tmp_path / "tuning.json").read_text(encoding="utf-8"))
    assert payload["best"] == "evidence_first"
    assert len(payload["variants"]) == 3


def test_tuning_tie_breaks_on_shorter_issue_list(tmp_path, monkeypatch):
    measured = {
        "baseline": _Summary(_aggregate(0.90), final_issues=12),
        "evidence_first": _Summary(_aggregate(0.90), final_issues=5),
        "coverage_first": _Summary(_aggregate(0.90), final_issues=9),
    }
    monkeypatch.setattr(
        "reqpilot.tuning.run_eval",
        lambda **kwargs: measured[kwargs["out_dir"].name],
    )
    report = tune_review_prompt(out_dir=tmp_path)
    assert report.best == "evidence_first"


def test_tuning_falls_back_when_no_variant_meets_the_budget(tmp_path, monkeypatch):
    measured = {
        "baseline": _Summary(_aggregate(0.80), final_issues=50),
        "evidence_first": _Summary(_aggregate(0.70), final_issues=40),
        "coverage_first": _Summary(_aggregate(0.60), final_issues=30),
    }
    monkeypatch.setattr(
        "reqpilot.tuning.run_eval",
        lambda **kwargs: measured[kwargs["out_dir"].name],
    )
    report = tune_review_prompt(out_dir=tmp_path, max_final_issues=20)
    assert report.best == "baseline"
    assert "没有变体满足" in report.reason
    assert all(not r.eligible for r in report.results)


def test_tuning_restores_the_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "reqpilot.tuning.run_eval",
        lambda **kwargs: _Summary(_aggregate(0.8), final_issues=5),
    )
    monkeypatch.delenv(PROMPT_VARIANT_ENV, raising=False)
    tune_review_prompt(variants=["baseline", "evidence_first"], out_dir=tmp_path)
    import os

    assert PROMPT_VARIANT_ENV not in os.environ


def test_tuning_rejects_empty_case_set(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "reqpilot.tuning.run_eval",
        lambda **kwargs: _Summary(_aggregate(0.8), case_count=0),
    )
    with pytest.raises(ValueError, match="没有可用的评测用例"):
        tune_review_prompt(variants=["baseline"], out_dir=tmp_path)
