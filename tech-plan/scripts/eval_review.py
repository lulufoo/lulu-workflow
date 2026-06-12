#!/usr/bin/env python3
"""Shared helpers for parsing eval review markdown files."""

from __future__ import annotations

import re
from pathlib import Path

_DIM_INDEX_TO_NAME = {"1": "e1", "2": "e2", "3": "e3"}
_REVIEW_FILE_RE = re.compile(r"tech-review-e\d+([123])\.md$")
_SEVERITY_RANK = {"critical": 3, "medium": 2, "minor": 1}


def split_table_row(line: str) -> list[str]:
    cells = line.strip().split("|")
    if len(cells) >= 3:
        return [cell.strip() for cell in cells[1:-1]]
    return [cell.strip() for cell in cells if cell.strip()]


def parse_review_issues(path: Path, *, dimension: str) -> list[dict[str, str]]:
    """Parse eval-runner review table rows from a tech-review markdown file."""
    if not path.exists():
        return []

    issues: list[dict[str, str]] = []
    header: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = split_table_row(line)
        if not cells:
            continue
        lowered = [cell.lower() for cell in cells]
        if "severity" in lowered and "status" in lowered and "decision" in lowered:
            header = lowered
            continue
        if not header:
            continue

        row = {
            header[i]: cells[i] if i < len(cells) else ""
            for i in range(len(header))
        }

        issue_id = row.get("id") or row.get("#") or ""
        description = row.get("description") or row.get("issue") or ""
        if not issue_id and not description:
            continue

        issues.append({
            "id": issue_id,
            "dimension": dimension,
            "location": row.get("location", ""),
            "severity": row.get("severity", ""),
            "description": description,
            "status": row.get("status", ""),
            "decision": row.get("decision", ""),
        })
    return issues


def dimension_from_review_path(path: Path) -> str:
    match = _REVIEW_FILE_RE.search(path.name)
    if not match:
        return ""
    return _DIM_INDEX_TO_NAME.get(match.group(1), "")


def collect_review_issues(
    eval_dir: Path,
) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[dict[str, str]] = []
    review_paths: list[str] = []
    if not eval_dir.is_dir():
        return issues, review_paths

    for path in sorted(eval_dir.glob("tech-review-e*.md")):
        dimension = dimension_from_review_path(path)
        if not dimension:
            continue
        review_paths.append(path.as_posix())
        issues.extend(parse_review_issues(path, dimension=dimension))
    return issues, review_paths


def build_dimensions(eval_state: dict[str, str]) -> list[dict[str, str]]:
    dimensions: list[dict[str, str]] = []
    for dim in ("e1", "e2", "e3"):
        status = eval_state.get(f"{dim}_status", "")
        if status in ("", "pending"):
            continue
        dimensions.append({
            "dim": dim,
            "status": status,
            "total": eval_state.get(f"{dim}_total_issues", "0"),
            "resolved": eval_state.get(f"{dim}_resolved_issues", "0"),
        })
    return dimensions


def count_ignored(issues: list[dict[str, str]]) -> int:
    return sum(
        1 for issue in issues if issue.get("decision", "").lower() == "ignore"
    )


def _reason_from_issue(issue: dict[str, str]) -> str:
    issue_id = issue.get("id", "")
    description = issue.get("description", "")
    if issue_id and description:
        return f"{issue_id}: {description}"
    return description or issue_id


def compute_fix_severity(
    issues: list[dict[str, str]],
) -> tuple[str, str]:
    """Return fix_severity and fix_severity_reason from parsed review issues."""
    if not issues:
        return "minor", ""

    ranked = sorted(
        issues,
        key=lambda issue: _SEVERITY_RANK.get(
            issue.get("severity", "").lower(),
            0,
        ),
        reverse=True,
    )
    top = ranked[0]
    severity = top.get("severity", "minor").lower()
    if severity not in _SEVERITY_RANK:
        severity = "minor"
    if all(issue.get("decision", "").lower() == "ignore" for issue in issues):
        severity = "minor"
    return severity, _reason_from_issue(top)


def build_issue_counts(
    eval_state: dict[str, str],
    issues: list[dict[str, str]],
) -> dict[str, int]:
    total_issues = int(eval_state.get("total_issues", "0") or "0")
    resolved_issues = int(eval_state.get("resolved_issues", "0") or "0")
    ignored_issues = count_ignored(issues)
    if ignored_issues == 0 and total_issues > resolved_issues:
        ignored_issues = total_issues - resolved_issues
    return {
        "total_issues": total_issues,
        "resolved_issues": resolved_issues,
        "ignored_issues": ignored_issues,
    }
