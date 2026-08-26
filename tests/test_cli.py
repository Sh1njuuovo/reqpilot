from reqpilot.cli import main


def test_smoke_cli(tmp_path):
    out = tmp_path / "smoke"
    assert main(["smoke", "--out", str(out)]) == 0
    assert (out / "summary.json").exists()
    assert (out / "prototype.html").exists()
    assert (out / "prd.md").exists()


def test_demo_cli(tmp_path):
    out = tmp_path / "demo"
    assert main(["demo", "--out", str(out)]) == 0
    assert (out / "tasks.md").exists()


def test_eval_cli(tmp_path):
    out = tmp_path / "eval"
    assert main(["eval", "--out", str(out)]) == 0
    assert list(out.glob("eval_mock_latest.json"))
