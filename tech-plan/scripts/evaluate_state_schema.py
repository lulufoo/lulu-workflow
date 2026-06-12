#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for tech-plan evaluate-state.md.

CLI:
    python3 evaluate_state_schema.py --schema
    python3 evaluate_state_schema.py --read  --path <evaluate-state.md>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from session_state_schema import load_active_doc_from_cycle
from workflow_common import doc_dir, parse_frontmatter_fields, read_md_field

_SCHEMA: list[dict] = [
    {"field": "version", "type": "string", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "phase", "type": "string", "required": True,
     "description": "Fixed value: evaluate"},
    {"field": "current_dimension", "type": "string", "required": True,
     "description": "Active eval dimension: e1 | e2 | e3 | done | abandoned"},
    {"field": "e1_status", "type": "string", "required": True,
     "description": "e1 dimension status"},
    {"field": "e1_total_issues", "type": "string", "required": True,
     "description": "e1 total issues count"},
    {"field": "e1_resolved_issues", "type": "string", "required": True,
     "description": "e1 resolved issues count"},
    {"field": "e2_status", "type": "string", "required": True,
     "description": "e2 dimension status"},
    {"field": "e2_total_issues", "type": "string", "required": True,
     "description": "e2 total issues count"},
    {"field": "e2_resolved_issues", "type": "string", "required": True,
     "description": "e2 resolved issues count"},
    {"field": "e3_status", "type": "string", "required": True,
     "description": "e3 dimension status"},
    {"field": "e3_total_issues", "type": "string", "required": True,
     "description": "e3 total issues count"},
    {"field": "e3_resolved_issues", "type": "string", "required": True,
     "description": "e3 resolved issues count"},
    {"field": "total_issues", "type": "string", "required": True,
     "description": "Aggregate total issues"},
    {"field": "resolved_issues", "type": "string", "required": True,
     "description": "Aggregate resolved issues"},
    {"field": "fix_severity", "type": "string", "required": True,
     "description": "Fix severity label when returning to Drafting"},
    {"field": "fix_severity_reason", "type": "string", "required": True,
     "description": "Fix severity reason"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}
_SCHEMA_FIELD_NAMES = _REQUIRED_FIELDS

_KEY_ORDER = [
    "version",
    "phase",
    "current_dimension",
    "e1_status",
    "e1_total_issues",
    "e1_resolved_issues",
    "e2_status",
    "e2_total_issues",
    "e2_resolved_issues",
    "e3_status",
    "e3_total_issues",
    "e3_resolved_issues",
    "total_issues",
    "resolved_issues",
    "fix_severity",
    "fix_severity_reason",
]

_VALID_MODES = frozenset({"product", "tech"})


def get_schema() -> list[dict]:
    """Return field definitions for evaluate-state.md."""
    return list(_SCHEMA)


def _base_fields() -> dict[str, str]:
    return {
        "version": "1",
        "phase": "evaluate",
        "e1_total_issues": "0",
        "e1_resolved_issues": "0",
        "e2_total_issues": "0",
        "e2_resolved_issues": "0",
        "e3_total_issues": "0",
        "e3_resolved_issues": "0",
        "total_issues": "0",
        "resolved_issues": "0",
        "fix_severity": "",
        "fix_severity_reason": "",
    }


def build_initial_evaluate_state(*, mode: str) -> dict[str, str]:
    """Return frontmatter fields for a new evaluate-state.md."""
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid mode: {mode!r} (allowed: {sorted(_VALID_MODES)})")

    data = _base_fields()
    if mode == "product":
        data.update(
            {
                "current_dimension": "e1",
                "e1_status": "pending",
                "e2_status": "pending",
                "e3_status": "pending",
            }
        )
    else:
        data.update(
            {
                "current_dimension": "e2",
                "e1_status": "complete",
                "e2_status": "pending",
                "e3_status": "pending",
            }
        )
    return data


def validate_evaluate_state(data: dict) -> list[str]:
    """Return list of validation error strings; empty means valid."""
    errors: list[str] = []
    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")
    if data.get("version") not in (None, "1"):
        errors.append(f"invalid version: {data.get('version')!r} (expected '1')")
    if data.get("phase") not in (None, "evaluate"):
        errors.append(f"invalid phase: {data.get('phase')!r} (expected 'evaluate')")
    return errors


def _serialize_frontmatter(data: dict) -> str:
    lines = ["---"]
    for key in _KEY_ORDER:
        if key in data:
            lines.append(f"{key}: {data[key]}")
    for key, value in data.items():
        if key not in _SCHEMA_FIELD_NAMES:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def save_evaluate_state(path: Path, data: dict, *, merge: bool = True) -> None:
    """Write evaluate-state.md with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and merge:
        existing = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
        merged = dict(existing)
        merged.update(data)
        data = merged

    errors = validate_evaluate_state(data)
    if errors:
        raise ValueError(f"evaluate-state data invalid: {'; '.join(errors)}")

    path.write_text(_serialize_frontmatter(data), encoding="utf-8")


def load_evaluate_state(path: Path) -> dict:
    """Read and validate evaluate-state.md."""
    if not path.exists():
        raise ValueError(f"evaluate-state.md not found: {path}")
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        raise ValueError(f"missing YAML frontmatter in {path}")
    fields = parse_frontmatter_fields(content)
    if not fields:
        raise ValueError(f"empty or invalid frontmatter in {path}")
    errors = validate_evaluate_state(fields)
    if errors:
        raise ValueError(f"evaluate-state invalid ({path}): {'; '.join(errors)}")
    return fields


def init_evaluate_state(path: Path, *, mode: str) -> None:
    """Initialize evaluate-state.md for a new evaluation round."""
    save_evaluate_state(path, build_initial_evaluate_state(mode=mode), merge=False)


def evaluate_state_path(cycle_id: str, doc_round: int) -> Path:
    return doc_dir(cycle_id, doc_round) / "evaluate-state.md"


def resolve_evaluate_state_path_from_cycle(cycle_id: str, project_root: Path) -> Path:
    """Resolve revision{N}/evaluate-state.md via session-state.md active_doc."""
    active_doc = load_active_doc_from_cycle(cycle_id, project_root)
    return project_root / evaluate_state_path(cycle_id, active_doc)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="evaluate-state schema I/O")
    parser.add_argument("--schema", action="store_true", help="Print field schema JSON")
    parser.add_argument("--read", action="store_true", help="Read and validate file")
    parser.add_argument("--path", type=Path, help="Path to evaluate-state.md")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), ensure_ascii=False, indent=2))
        return 0

    if args.read:
        if not args.path:
            print("--read requires --path", file=sys.stderr)
            return 1
        print(json.dumps(load_evaluate_state(args.path.resolve()), ensure_ascii=False))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
