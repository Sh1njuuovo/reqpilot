import reqpilot.cli as cli_module
from reqpilot.eval import runner as eval_runner
from reqpilot.pipeline import run_pipeline as real_run_pipeline

real_run_eval = eval_runner.run_eval


def _fake_run_pipeline(*args, **kwargs):
    kwargs["provider_name"] = "mock"
    return real_run_pipeline(*args, **kwargs)


def _fake_run_eval(*args, **kwargs):
    kwargs["provider_name"] = "mock"
    return real_run_eval(*args, **kwargs)


def test_smoke_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "run_pipeline", _fake_run_pipeline)
    out = tmp_path / "smoke"
    assert cli_module.main(["smoke", "--out", str(out)]) == 0
    assert (out / "summary.json").exists()
    assert (out / "prototype.html").exists()
    assert (out / "prd.md").exists()


def test_demo_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "run_pipeline", _fake_run_pipeline)
    out = tmp_path / "demo"
    assert cli_module.main(["demo", "--out", str(out)]) == 0
    assert (out / "tasks.md").exists()


def test_eval_cli(tmp_path, monkeypatch):
    monkeypatch.setattr(eval_runner, "run_eval", _fake_run_eval)
    out = tmp_path / "eval"
    assert cli_module.main(["eval", "--out", str(out)]) == 0
    assert list(out.glob("eval_llm_keyword_latest.json")) or list(out.glob("eval_mock_keyword_latest.json"))
