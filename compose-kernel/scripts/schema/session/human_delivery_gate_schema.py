#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for compose stage human-delivery-gate.md.

CLI:
    python3 human_delivery_gate_schema.py --schema
    python3 human_delivery_gate_schema.py --read  --path <human-delivery-gate.md>
    python3 human_delivery_gate_schema.py --write --path <human-delivery-gate.md> [--note TEXT]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import sys

_SCRIPTS = Path(__file__).resolve().parents[2]
_CORE = _SCRIPTS / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from workflow_common import parse_frontmatter_fields
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID
from workflow_profile_paths import approval_path

_SCHEMA: list[dict] = [
    {"field": "approved", "type": "string", "required": True,
     "description": "Must be true after user confirms delivery"},
    {"field": "approved_at", "type": "string", "required": True,
     "description": "ISO 8601 timestamp of delivery confirmation"},
    {"field": "note", "type": "string", "required": False,
     "description": "Optional delivery note"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}
_OPTIONAL_SCHEMA_FIELDS = {s["field"] for s in _SCHEMA if not s["required"]}
_SCHEMA_FIELD_NAMES = _REQUIRED_FIELDS | _OPTIONAL_SCHEMA_FIELDS

_REQUIRED_KEY_ORDER = ["approved", "approved_at"]


def get_schema() -> list[dict]:
    """Return field definitions for human-delivery-gate.md."""
    return list(_SCHEMA)


def validate_delivery_gate(data: dict) -> list[str]:
    """Return list of validation error strings; empty means valid."""
    errors: list[str] = []

    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")

    if data.get("approved") not in (None, "true"):
        errors.append(f"invalid approved: {data.get('approved')!r} (expected 'true')")

    return errors


def _serialize_frontmatter(data: dict) -> str:
    lines = ["---"]
    for key in _REQUIRED_KEY_ORDER:
        if key in data:
            lines.append(f"{key}: {data[key]}")
    for key in sorted(_OPTIONAL_SCHEMA_FIELDS):
        if key in data:
            lines.append(f"{key}: {data[key]}")
    for key, value in data.items():
        if key not in _SCHEMA_FIELD_NAMES:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def save_delivery_gate(path: Path, data: dict, *, merge: bool = True) -> None:
    """Write human-delivery-gate.md with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and merge:
        existing = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
        merged = dict(existing)
        merged.update(data)
        data = merged

    payload = dict(data)
    if "approved_at" not in payload or not merge:
        payload.setdefault(
            "approved_at",
            datetime.now(timezone.utc).isoformat(),
        )

    errors = validate_delivery_gate(payload)
    if errors:
        raise ValueError(f"human-delivery-gate data invalid: {'; '.join(errors)}")

    path.write_text(_serialize_frontmatter(payload), encoding="utf-8")


def load_delivery_gate(path: Path) -> dict:
    """Read and validate human-delivery-gate.md; raise ValueError if missing or invalid."""
    if not path.exists():
        raise ValueError(f"human-delivery-gate.md not found: {path}")
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        raise ValueError(f"missing YAML frontmatter in {path}")
    fields = parse_frontmatter_fields(content)
    if not fields:
        raise ValueError(f"empty or invalid frontmatter in {path}")
    errors = validate_delivery_gate(fields)
    if errors:
        raise ValueError(f"human-delivery-gate.md invalid ({path}): {'; '.join(errors)}")
    return fields


def delivery_gate_exists(path: Path) -> bool:
    """Return True if a valid human-delivery-gate.md exists at path."""
    try:
        load_delivery_gate(path)
        return True
    except ValueError:
        return False


def write_approved(path: Path, *, note: str = "") -> None:
    """Write human-delivery-gate.md after user confirms delivery."""
    data: dict[str, str] = {
        "approved": "true",
        "approved_at": datetime.now(timezone.utc).isoformat(),
    }
    if note:
        data["note"] = note
    save_delivery_gate(path, data, merge=False)


def resolve_delivery_gate_path(
    cycle_id: str,
    doc_round: int,
    project_root: Path,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    """Return revision{N}/human-delivery-gate.md path."""
    return project_root / approval_path(cycle_id, doc_round, profile_id)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="compose stage human-delivery-gate.md schema utilities")
    parser.add_argument("--schema", action="store_true", help="Print JSON schema array and exit")
    parser.add_argument("--read", action="store_true", help="Print delivery gate as JSON")
    parser.add_argument("--write", action="store_true", help="Write approved delivery gate")
    parser.add_argument("--path", type=Path, help="Path to human-delivery-gate.md")
    parser.add_argument("--note", type=str, default="", help="Optional note for --write")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    if args.read:
        if not args.path:
            parser.error("--read requires --path")
        try:
            data = load_delivery_gate(args.path)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    if args.write:
        if not args.path:
            parser.error("--write requires --path")
        try:
            write_approved(args.path, note=args.note)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
