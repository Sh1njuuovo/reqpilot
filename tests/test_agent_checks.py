import json

from reqpilot.agent.checks import review_fix_verifier
from reqpilot.agent.sandbox import WorkspaceSandbox


def _write_issues(root, items):
    (root / "issues.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")


def _verify(root):
    return review_fix_verifier(WorkspaceSandbox(root))()


def test_empty_workspace_fails_with_readable_checks(tmp_path):
    ok, checks = _verify(tmp_path)
    assert ok is False
    assert any("issues.json" in check for check in checks)
    assert any("tasks.md" in check for check in checks)


def test_broken_issues_json_is_reported(tmp_path):
    (tmp_path / "issues.json").write_text("{not json", encoding="utf-8")
    ok, checks = _verify(tmp_path)
    assert ok is False
    assert any("不是合法 JSON" in check for check in checks)


def test_every_blocking_issue_must_be_answered(tmp_path):
    _write_issues(
        tmp_path,
        [
            {"id": "ISSUE-001", "severity": "critical"},
            {"id": "ISSUE-002", "severity": "major"},
            {"id": "ISSUE-003", "severity": "minor"},
        ],
    )
    (tmp_path / "tasks.md").write_text("# 任务清单\n- T1 补充幂等校验\n", encoding="utf-8")
    (tmp_path / "review-fixes.md").write_text(
        "# 整改结论\n- ISSUE-001 已在 PRD 3.2 补充幂等校验说明\n", encoding="utf-8"
    )
    ok, checks = _verify(tmp_path)
    assert ok is False
    assert any("ISSUE-002" in check for check in checks)


def test_verifier_passes_when_all_blocking_issues_are_covered(tmp_path):
    _write_issues(
        tmp_path,
        [
            {"id": "ISSUE-001", "severity": "critical"},
            {"id": "ISSUE-002", "severity": "major"},
            {"id": "ISSUE-003", "severity": "minor"},
        ],
    )
    (tmp_path / "tasks.md").write_text("# 任务清单\n- T1 补充幂等校验\n", encoding="utf-8")
    (tmp_path / "review-fixes.md").write_text(
        "# 整改结论\n- ISSUE-001 已补充幂等校验\n- ISSUE-002 已补充分页上限说明\n",
        encoding="utf-8",
    )
    ok, checks = _verify(tmp_path)
    assert ok is True
    assert any("阻塞问题已全部覆盖" in check for check in checks)


def test_minor_only_issue_list_needs_no_per_issue_answer(tmp_path):
    _write_issues(tmp_path, [{"id": "ISSUE-001", "severity": "minor"}])
    (tmp_path / "tasks.md").write_text("# 任务清单\n- T1 调整文案\n", encoding="utf-8")
    (tmp_path / "review-fixes.md").write_text(
        "# 整改结论\n本次没有阻塞级问题，仅记录 minor 项待优化。\n", encoding="utf-8"
    )
    ok, _ = _verify(tmp_path)
    assert ok is True
