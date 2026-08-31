#!/usr/bin/env python3
"""Parse and filter eval review markdown table rows (workflow-agnostic)."""

from __future__ import annotations

import re
from pathlib import Path

_REVIEW_COLUMNS = [
    "id",
    "root_cause",
    "handling_mode",
    "sot_ref",
    "location",
    "severity",
    "evidence",
    "description",
    "status",
    "decision",
    "resolution",
]


def split_table_row(line: str) -> list[str]:
    cells = line.strip().split("|")
    if len(cells) >= 3:
        return [cell.strip() for cell in cells[1:-1]]
    return [cell.strip() for cell in cells if cell.strip()]


def parse_review_frontmatter(content: str) -> dict[str, str]:
    """Parse scalar ReviewFile frontmatter fields."""
    match = re.match(r"^---\s*\n(.*?)\n---(?:\s*\n|$)", content, re.DOTALL)
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    return fields


def parse_review_file(
    path: Path,
    *,
    expected_dimension_id: str | None = None,
    expected_round_token: str | None = None,
) -> list[dict[str, str]]:
    """Parse all issue rows from a review markdown file."""
    if not path.exists():
        return []
    return parse_review_content(
        path.read_text(encoding="utf-8"),
        expected_dimension_id=expected_dimension_id,
        expected_round_token=expected_round_token,
    )


def parse_review_content(
    content: str,
    *,
    expected_dimension_id: str | None = None,
    expected_round_token: str | None = None,
) -> list[dict[str, str]]:
    """Parse all issue rows from review markdown content."""
    frontmatter = parse_review_frontmatter(content)
    if frontmatter.get("schema_version") != "3":
        raise ValueError(
            "incompatible_round: ReviewFile schema_version "
            f"{frontmatter.get('schema_version')!r} is not supported "
            "(expected '3')",
        )
    for field in ("dimension_id", "round_token"):
        if not frontmatter.get(field):
            raise ValueError(
                f"invalid ReviewFile v3 identity: missing {field}",
            )
    if (
        expected_dimension_id is not None
        and frontmatter["dimension_id"] != expected_dimension_id
    ):
        raise ValueError(
            "ReviewFile dimension_id mismatch: "
            f"expected {expected_dimension_id!r}, "
            f"got {frontmatter['dimension_id']!r}",
        )
    if (
        expected_round_token is not None
        and frontmatter["round_token"] != expected_round_token
    ):
        raise ValueError(
            "ReviewFile round_token mismatch: "
            f"expected {expected_round_token!r}, "
            f"got {frontmatter['round_token']!r}",
        )
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
        if not header:
            if lowered != _REVIEW_COLUMNS:
                raise ValueError(
                    "invalid ReviewFile v3 header: expected exact column sequence",
                )
            header = lowered
            continue
        if len(cells) != len(_REVIEW_COLUMNS):
            raise ValueError(
                f"invalid ReviewFile row: expected {len(_REVIEW_COLUMNS)} cells, "
                f"got {len(cells)}",
            )

        row = {header[i]: cells[i] for i in range(len(header))}

        issue_id = row.get("id", "")
        description = row.get("description", "")
        if not issue_id and not description:
            continue

        issues.append({
            "id": issue_id,
            "root_cause": row.get("root_cause", ""),
            "handling_mode": row.get("handling_mode", ""),
            "sot_ref": row.get("sot_ref", ""),
            "location": row.get("location", ""),
            "severity": row.get("severity", ""),
            "evidence": row.get("evidence", ""),
            "description": description,
            "status": row.get("status", ""),
            "decision": row.get("decision", ""),
            "resolution": row.get("resolution", ""),
        })
    if not header:
        raise ValueError("invalid ReviewFile v3 header: header row not found")
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


def rows_by_handling_mode(
    rows: list[dict[str, str]],
    handling_mode: str,
) -> list[dict[str, str]]:
    """Filter rows by their persisted immutable handling mode."""
    return [
        row
        for row in rows
        if row.get("handling_mode", "").lower() == handling_mode.lower()
    ]


def count_resolved(rows: list[dict[str, str]]) -> int:
    """Count rows whose lifecycle status is resolved."""
    return sum(
        1 for row in rows if row.get("status", "").lower() == "resolved"
    )


def nonterminal_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Return findings that have not reached a legal completion disposition."""
    return pending_rows(rows)


def has_escalated(rows: list[dict[str, str]]) -> bool:
    return any(
        row.get("status", "").lower() == "resolved"
        and row.get("decision", "").lower() == "escalate"
        for row in rows
    )
