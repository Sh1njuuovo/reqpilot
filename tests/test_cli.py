import json

import reqpilot.cli as cli_module
from reqpilot.eval import runner as eval_runner
from reqpilot.pipeline import run_pipeline as real_run_pipeline
from reqpilot.providers.scripted import ScriptedAgentProvider, finish

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


def test_demo_bundle_carries_the_raw_requirement(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "run_pipeline", _fake_run_pipeline)
    out = tmp_path / "demo"
    assert cli_module.main(["demo", "--out", str(out)]) == 0
    assert "审批" in (out / "requirement.md").read_text(encoding="utf-8")


def _prepare_workspace(path):
    path.mkdir(parents=True, exist_ok=True)
    (path / "issues.json").write_text(
        json.dumps([{"id": "ISSUE-001", "severity": "critical"}], ensure_ascii=False),
        encoding="utf-8",
    )
    (path / "tasks.md").write_text("# 任务清单\n- T1 补充幂等校验\n", encoding="utf-8")
    (path / "review-fixes.md").write_text(
        "# 整改结论\n- ISSUE-001 已补充幂等校验说明\n", encoding="utf-8"
    )
    return path


def test_agent_cli_runs_verified_goal(tmp_path, monkeypatch):
    workspace = _prepare_workspace(tmp_path / "demo")
    monkeypatch.setattr(
        "reqpilot.providers.get_provider",
        lambda name, settings: ScriptedAgentProvider([finish("已经完成")]),
    )
    out = tmp_path / "agent"
    assert cli_module.main(["agent", "--workspace", str(workspace), "--out", str(out)]) == 0

    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "completed"
    assert summary["completion_verified"] is True
    assert (out / "agent-run.json").exists()
    assert (out / "agent-transcript.json").exists()


def test_agent_cli_requires_a_demo_workspace(tmp_path, capsys):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cli_module.main(["agent", "--workspace", str(empty)]) == 1
    assert "issues.json" in capsys.readouterr().err
