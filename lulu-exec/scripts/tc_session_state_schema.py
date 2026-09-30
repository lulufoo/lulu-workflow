#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for lulu-exec session-state.md.

CLI:
    python3 session_state_schema.py --schema
    python3 session_state_schema.py --read  --path <session-state.md>
    python3 session_state_schema.py --next  --path <session-state.md>
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from tc_workflow_common import read_md_field

_CODE_SCHEMA: list[dict] = [
    {"field": "version", "type": "int", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "active_session", "type": "int", "required": True,
     "description": "Active code session round (maps to s{N}/)"},
    {"field": "updated_at", "type": "string", "required": True,
     "description": "ISO 8601 last-update timestamp"},
]

_REQUIRED_FIELDS = {s["field"] for s in _CODE_SCHEMA if s["required"]}


def get_schema() -> list[dict]:
    """Return field definitions for lulu-exec session-state.md."""
    return list(_CODE_SCHEMA)


def load_session_state(path: Path) -> int:
    """Read active_session from session-state.md; raise ValueError if missing or invalid."""
    if not path.exists():
        raise ValueError(f"session-state.md not found: {path}")
    raw = read_md_field(path, "active_session", default="")
    if not raw:
        raise ValueError(f"active_session not found in {path}")
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"active_session must be an integer in {path}, got {raw!r}") from exc


def save_session_state(path: Path, active_session: int) -> None:
    """Write session-state.md with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    content = (
        f"---\n"
        f"version: 1\n"
        f"active_session: {active_session}\n"
        f"updated_at: {now}\n"
        f"---\n"
    )
    path.write_text(content, encoding="utf-8")


def next_session_round(path: Path) -> int:
    """Return next session round: 1 if absent, else current active_session + 1."""
    if not path.exists():
        return 1
    try:
        return load_session_state(path) + 1
    except ValueError:
        return 1


def load_work_order_round(path: Path) -> str:
    """Read work-order round from session-state.md.

    Prefer active_doc (current contract), fallback to active_session
    for backward compatibility with older fixtures.
    """
    if not path.exists():
        raise ValueError(f"session-state.md not found: {path}")
    active_doc = read_md_field(path, "active_doc", default="")
    if active_doc:
        return active_doc
    active_session = read_md_field(path, "active_session", default="")
    if active_session:
        return active_session
    raise ValueError(f"active_doc/active_session not found in {path}")


def _cli() -> int:
    p = argparse.ArgumentParser(description="session-state.md schema utilities")
    p.add_argument("--schema", action="store_true", help="Print JSON schema array and exit")
    p.add_argument("--read", action="store_true", help="Print active_session from --path")
    p.add_argument("--next", action="store_true", help="Compute, write, and print next session round")
    p.add_argument("--path", type=Path, help="Path to session-state.md")
    args = p.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    if not args.path:
        p.error("--path is required for --read and --next")

    if args.read:
        print(load_session_state(args.path))
        return 0

    if args.next:
        n = next_session_round(args.path)
        save_session_state(args.path, n)
        print(n)
        return 0

    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
