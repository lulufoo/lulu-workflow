#!/usr/bin/env python3
"""Review table schema and validation for eval review markdown files.

CLI:
    python3 review_schema.py --schema
    python3 review_schema.py --validate --path <review.md>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Literal

from review_io import split_table_row

Phase = Literal["probe", "remediation"]

_SCHEMA: dict = {
    "version": "1",
    "columns": [
        "id",
        "root_cause",
        "sot_ref",
        "location",
        "severity",
        "evidence",
        "description",
        "status",
        "decision",
        "resolution",
    ],
    "enums": {
        "root_cause": [
            "SOT-DEFECT",
            "WO-MISS",
            "WO-ERROR",
            "UNRESOLVABLE",
            "DECISION-REQUIRED",
        ],
        "severity": ["critical", "medium", "minor"],
        "status_probe": ["pending"],
        "status_remediation": ["fixed", "ignored", "escalated", "reclassified"],
        "decision_probe": ["—"],
        "decision_remediation": ["fix", "ignore", "escalate", "reclassify"],
    },
    "required_at_probe": [
        "id",
        "root_cause",
        "location",
        "severity",
        "evidence",
        "description",
        "status",
    ],
    "sot_ref_required_when": ["SOT-DEFECT", "WO-MISS"],
}

_SOT_REF_REQUIRED = frozenset(_SCHEMA["sot_ref_required_when"])
_ROOT_CAUSES = frozenset(_SCHEMA["enums"]["root_cause"])
_SEVERITIES = frozenset(_SCHEMA["enums"]["severity"])
_STATUS_PROBE = frozenset(_SCHEMA["enums"]["status_probe"])
_STATUS_REMEDIATION = frozenset(_SCHEMA["enums"]["status_remediation"])
_DECISION_PROBE = frozenset(_SCHEMA["enums"]["decision_probe"])
_DECISION_REMEDIATION = frozenset(_SCHEMA["enums"]["decision_remediation"])


def get_schema() -> dict:
    """Return review table schema dict."""
    return dict(_SCHEMA)


def _normalize_header(cells: list[str]) -> list[str]:
    return [cell.strip().lower() for cell in cells]


def validate_review_header(lines: list[str]) -> list[str]:
    """Validate table header row matches schema columns."""
    errors: list[str] = []
    expected = [col.lower() for col in _SCHEMA["columns"]]
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---"):
            continue
        cells = split_table_row(stripped)
        if not cells:
            continue
        lowered = _normalize_header(cells)
        if "severity" in lowered and "status" in lowered:
            if lowered != expected:
                errors.append(
                    f"header columns {lowered!r} do not match schema {expected!r}"
                )
            return errors
    errors.append("review table header row not found")
    return errors


def validate_issue_row(row: dict[str, str], *, phase: Phase) -> list[str]:
    """Validate a single parsed issue row."""
    errors: list[str] = []
    issue_id = row.get("id", "")
    if not issue_id:
        errors.append("missing required field: id")

    root_cause = row.get("root_cause", "").upper()
    if not root_cause:
        errors.append(f"{issue_id or '?'}: missing required field: root_cause")
    elif root_cause not in _ROOT_CAUSES:
        errors.append(f"{issue_id}: invalid root_cause: {root_cause!r}")

    location = row.get("location", "")
    if not location:
        errors.append(f"{issue_id}: missing required field: location")

    severity = row.get("severity", "").lower()
    if not severity:
        errors.append(f"{issue_id}: missing required field: severity")
    elif severity not in _SEVERITIES:
        errors.append(f"{issue_id}: invalid severity: {severity!r}")

    evidence = row.get("evidence", "")
    if not evidence:
        errors.append(f"{issue_id}: missing required field: evidence")

    description = row.get("description", "")
    if not description:
        errors.append(f"{issue_id}: missing required field: description")

    status = row.get("status", "").lower()
    if not status:
        errors.append(f"{issue_id}: missing required field: status")
    elif phase == "probe":
        if status not in _STATUS_PROBE:
            errors.append(f"{issue_id}: invalid probe status: {status!r}")
    elif status not in _STATUS_REMEDIATION:
        errors.append(f"{issue_id}: invalid remediation status: {status!r}")

    decision = row.get("decision", "")
    if phase == "probe":
        if decision not in _DECISION_PROBE and decision != "—":
            errors.append(f"{issue_id}: invalid probe decision: {decision!r}")
    elif decision.lower() not in _DECISION_REMEDIATION:
        errors.append(f"{issue_id}: invalid remediation decision: {decision!r}")

    resolution = row.get("resolution", "")
    if phase == "probe" and resolution and root_cause != "WO-ERROR":
        errors.append(
            f"{issue_id}: probe resolution must be empty except for WO-ERROR",
        )

    sot_ref = row.get("sot_ref", "")
    if root_cause in _SOT_REF_REQUIRED and not sot_ref.strip():
        errors.append(f"{issue_id}: sot_ref required for root_cause {root_cause}")

    return errors


def validate_review_content(content: str, *, phase: Phase = "probe") -> list[str]:
    """Validate review text before it is persisted.

    Row phase is inferred per row: ``pending`` → probe rules; otherwise remediation.
    The ``phase`` parameter is retained for call-site documentation only.
    """
    lines = content.splitlines()
    errors = validate_review_header(lines)
    if errors:
        return errors

    header = [
        cell.strip().lower()
        for line in lines
        if line.strip().startswith("|") and not line.strip().startswith("|---")
        for cells in [split_table_row(line)]
        if "severity" in cells and "status" in cells and "decision" in cells
        for cell in cells
    ]
    rows: list[dict[str, str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---"):
            continue
        cells = split_table_row(stripped)
        if not cells or _normalize_header(cells) == header:
            continue
        if not header:
            continue
        if len(cells) != len(header):
            errors.append(
                f"review row has {len(cells)} cells, expected {len(header)}",
            )
            continue
        rows.append({header[i]: cells[i] for i in range(len(header))})
    for row in rows:
        row_phase: Phase = (
            "probe" if row.get("status", "").lower() == "pending" else "remediation"
        )
        errors.extend(validate_issue_row(row, phase=row_phase))
    return errors


def validate_review_file(path: Path, *, phase: Phase = "probe") -> list[str]:
    """Validate review file header and all issue rows."""
    if not path.exists():
        return [f"review file not found: {path}"]
    return validate_review_content(path.read_text(encoding="utf-8"), phase=phase)


def render_review_header(
    *,
    dim_label: str,
    rev: int,
    round_num: int,
    date: str,
    refs: str,
) -> str:
    """Render review file header from template placeholders."""
    return (
        f"# Tech Review — {dim_label} | revision{rev} round {round_num}\n\n"
        f"**Date:** {date}\n"
        f"**Refs:** {refs}\n\n"
        "| ID | root_cause | sot_ref | location | severity | evidence "
        "| description | status | decision | resolution |\n"
        "|----|------------|---------|----------|----------|----------"
        "|-------------|--------|----------|------------|\n"
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="eval review schema")
    parser.add_argument("--schema", action="store_true", help="Print schema JSON")
    parser.add_argument("--validate", action="store_true", help="Validate review file")
    parser.add_argument("--path", type=Path, help="Path to review markdown file")
    parser.add_argument(
        "--phase",
        choices=["probe", "remediation"],
        default="probe",
        help="Validation phase",
    )
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), ensure_ascii=False, indent=2))
        return 0

    if args.validate:
        if not args.path:
            print("--validate requires --path", file=sys.stderr)
            return 1
        errors = validate_review_file(args.path.resolve(), phase=args.phase)
        if errors:
            for err in errors:
                print(err, file=sys.stderr)
            return 1
        print(json.dumps({"ok": True, "path": str(args.path.resolve())}))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
