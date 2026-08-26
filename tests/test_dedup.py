from reqpilot.models import ReviewIssue
from reqpilot.review.dedup import deduplicate, finalize_issues, prune_issues


def _issue(role, title, category="completeness", severity="major"):
    return ReviewIssue(role=role, category=category, severity=severity, title=title)


def test_dedup_merges_cross_role_same_title():
    a = _issue("product", "缺少验收标准")
    b = _issue("test", "缺少验收标准")
    merged, removed = deduplicate([a, b])
    assert removed == 1
    assert len(merged) == 1
    assert set(merged[0].roles) == {"product", "test"}


def test_dedup_merges_evidence():
    a = ReviewIssue(role="backend", category="data", severity="minor", title="x", evidence=["a"])
    b = ReviewIssue(role="test", category="data", severity="major", title="x", evidence=["a", "b"])
    merged, removed = deduplicate([a, b])
    assert removed == 1
    assert set(merged[0].evidence) == {"a", "b"}
    assert merged[0].severity == "major"


def test_finalize_assigns_ids_and_sorts():
    critical = _issue("product", "严重问题", severity="critical")
    suggestion = _issue("test", "小建议", severity="suggestion")
    merged, removed = finalize_issues([suggestion, critical])
    assert removed == 0
    assert [i.id for i in merged] == ["ISSUE-001", "ISSUE-002"]
    assert merged[0].severity == "critical"
    assert merged[1].roles == ["test"]


def test_prune_issues_caps_per_role_by_severity():
    issues = [
        _issue("product", f"P{i}", severity="minor" if i < 7 else "critical")
        for i in range(8)
    ]
    pruned = prune_issues(issues, max_per_role=5)
    assert len(pruned) == 5
    assert sum(1 for i in pruned if i.severity == "critical") == 1
    assert sum(1 for i in pruned if i.severity == "minor") == 4
