#!/usr/bin/env python3
"""Parse and filter eval review markdown table rows (workflow-agnostic)."""

from __future__ import annotations

from pathlib import Path

_ARTIFACT_LABELS = frozenset({"WO-MISS", "WO-ERROR"})
_HUMAN_LABELS = frozenset({
    "SOT-DEFECT",
    "UNRESOLVABLE",
    "DECISION-REQUIRED",
})
_TERMINAL_STATUSES = frozenset({
    "fixed",
    "ignored",
    "reclassified",
    "accepted-divergence",
})


def split_table_row(line: str) -> list[str]:
    cells = line.strip().split("|")
    if len(cells) >= 3:
        return [cell.strip() for cell in cells[1:-1]]
    return [cell.strip() for cell in cells if cell.strip()]


def parse_review_file(path: Path) -> list[dict[str, str]]:
    """Parse all issue rows from a review markdown file."""
    if not path.exists():
        return []
    return parse_review_content(path.read_text(encoding="utf-8"))


def parse_review_content(content: str) -> list[dict[str, str]]:
    """Parse all issue rows from review markdown content."""
    issues: list[dict[str, str]] = []
    header: list[str] = []
    for raw_line in content.splitlines():
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
            "root_cause": row.get("root_cause", ""),
            "sot_ref": row.get("sot_ref", ""),
            "location": row.get("location", ""),
            "severity": row.get("severity", ""),
            "evidence": row.get("evidence", ""),
            "description": description,
            "status": row.get("status", ""),
            "decision": row.get("decision", ""),
            "resolution": row.get("resolution", ""),
        })
    return issues


def issues_by_root_cause(
    rows: list[dict[str, str]],
    labels: frozenset[str],
) -> list[dict[str, str]]:
    """Filter rows whose root_cause (case-insensitive) is in labels."""
    normalized = {label.upper() for label in labels}
    return [
        row for row in rows
        if row.get("root_cause", "").upper() in normalized
    ]


def pending_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return rows with status pending (case-insensitive)."""
    return [row for row in rows if row.get("status", "").lower() == "pending"]


def is_artifact_row(row: dict[str, str]) -> bool:
    """Return whether a row belongs to the Artifact handling class."""
    return row.get("root_cause", "").upper() in _ARTIFACT_LABELS


def pending_artifact_rows(
    rows: list[dict[str, str]],
    *,
    force_human_resolution: bool,
) -> list[dict[str, str]]:
    artifact_rows = issues_by_root_cause(rows, _ARTIFACT_LABELS)
    required_status = "approved" if force_human_resolution else "pending"
    return [
        row for row in artifact_rows
        if row.get("status", "").lower() == required_status
    ]


def pending_human_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return pending_rows(issues_by_root_cause(rows, _HUMAN_LABELS))


def pending_resolution_rows(
    rows: list[dict[str, str]],
    *,
    force_human_resolution: bool,
) -> list[dict[str, str]]:
    """Return rows that still require a Human Resolution disposition."""
    if force_human_resolution:
        return pending_rows(rows)
    return pending_human_rows(rows)


def count_resolved(rows: list[dict[str, str]]) -> int:
    """Count rows with terminal resolved dispositions."""
    resolved_statuses = frozenset({
        "fixed",
        "reclassified",
        "accepted-divergence",
    })
    return sum(
        1 for row in rows
        if row.get("status", "").lower() in resolved_statuses
    )


def nonterminal_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return findings that have not reached a legal completion disposition."""
    return [
        row for row in rows
        if row.get("status", "").lower() not in _TERMINAL_STATUSES
    ]


def has_pending_human(rows: list[dict[str, str]]) -> bool:
    return bool(pending_human_rows(rows))


def has_escalated(rows: list[dict[str, str]]) -> bool:
    return any(row.get("status", "").lower() == "escalated" for row in rows)
