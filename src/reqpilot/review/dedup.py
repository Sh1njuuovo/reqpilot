"""Issue deduplication, merging, and finalization."""

from __future__ import annotations

import re
from collections import defaultdict

from reqpilot.models import ReviewIssue, Severity

SEVERITY_ORDER: dict[Severity, int] = {"critical": 0, "major": 1, "minor": 2, "suggestion": 3}


def _normalize_title(title: str) -> str:
    return re.sub(r"[\s，。！？、,.!?()（）\[\]【】:：;；\-_]+", "", title.lower())[:24]


def issue_dedup_key(issue: ReviewIssue) -> str:
    return f"{issue.category}:{_normalize_title(issue.title)}"


def deduplicate(issues: list[ReviewIssue]) -> tuple[list[ReviewIssue], int]:
    """Merge issues sharing a dedup key; return (merged, removed_count)."""

    groups: dict[str, ReviewIssue] = {}
    for issue in issues:
        key = issue_dedup_key(issue)
        issue.dedup_key = key
        if key not in groups:
            issue.roles = [issue.role]
            groups[key] = issue
            continue
        existing = groups[key]
        if issue.role not in existing.roles:
            existing.roles.append(issue.role)
        for ev in issue.evidence:
            if ev not in existing.evidence:
                existing.evidence.append(ev)
        if SEVERITY_ORDER[issue.severity] < SEVERITY_ORDER[existing.severity]:
            existing.severity = issue.severity
        if issue.suggestion and issue.suggestion not in existing.suggestion:
            existing.suggestion = f"{existing.suggestion}；{issue.suggestion}".strip("；")
    merged = list(groups.values())
    return merged, len(issues) - len(merged)


def finalize_issues(issues: list[ReviewIssue]) -> tuple[list[ReviewIssue], int]:
    """Deduplicate, assign stable ids, and sort by severity."""

    merged, removed = deduplicate(issues)
    merged.sort(key=lambda i: (SEVERITY_ORDER[i.severity], i.role, i.title))
    for idx, issue in enumerate(merged, start=1):
        issue.id = f"ISSUE-{idx:03d}"
        if not issue.roles:
            issue.roles = [issue.role]
    return merged, removed


def prune_issues(issues: list[ReviewIssue], max_per_role: int = 5) -> list[ReviewIssue]:
    """Keep the top-N most severe issues per role (LLM output guardrail)."""

    by_role: dict[str, list[ReviewIssue]] = defaultdict(list)
    for issue in issues:
        by_role[issue.role].append(issue)
    pruned: list[ReviewIssue] = []
    for role_issues in by_role.values():
        role_issues.sort(key=lambda i: (SEVERITY_ORDER[i.severity], i.title))
        pruned.extend(role_issues[:max_per_role])
    pruned.sort(key=lambda i: (SEVERITY_ORDER[i.severity], i.role, i.title))
    return pruned
