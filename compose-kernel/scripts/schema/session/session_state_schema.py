#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for compose stage session-state.md.

CLI:
    python3 session_state_schema.py --schema
    python3 session_state_schema.py --read  --cycle-id <id> [--project-root .]
    python3 session_state_schema.py --read  --path <session-state.md>
    python3 session_state_schema.py --next  --cycle-id <id> [--project-root .]
    python3 session_state_schema.py --next  --path <session-state.md>
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

from workflow_common import read_md_field
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID
from workflow_profile_paths import session_state_path

_SCHEMA: list[dict] = [
    {"field": "version", "type": "int", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "active_doc", "type": "int", "required": True,
     "description": "Active tech-doc round (maps to revision{N}/)"},
    {"field": "updated_at", "type": "string", "required": True,
     "description": "ISO 8601 last-update timestamp"},
]


def get_schema() -> list[dict]:
    """Return field definitions for compose stage session-state.md."""
    return list(_SCHEMA)


def resolve_path(
    cycle_id: str,
    project_root: Path = Path("."),
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    """Return absolute path to session-state.md for a cycle."""
    return project_root / session_state_path(cycle_id, profile_id)


def load_active_doc(path: Path, *, default: int | None = None) -> int:
    """Read active_doc from session-state.md."""
    if not path.exists():
        if default is not None:
            return default
        raise ValueError(f"session-state.md not found: {path}")
    raw = read_md_field(path, "active_doc", default="")
    if not raw:
        if default is not None:
            return default
        raise ValueError(f"active_doc not found in {path}")
    try:
        return int(raw)
    except ValueError as exc:
        if default is not None:
            return default
        raise ValueError(
            f"active_doc must be an integer in {path}, got {raw!r}"
        ) from exc


def load_active_doc_from_cycle(
    cycle_id: str,
    project_root: Path,
    *,
    default: int = 1,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> int:
    """Read active_doc for a cycle; missing or invalid values fall back to default."""
    return load_active_doc(
        resolve_path(cycle_id, project_root, profile_id),
        default=default,
    )


def save_active_doc(path: Path, active_doc: int) -> None:
    """Write session-state.md with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    content = (
        f"---\n"
        f"version: 1\n"
        f"active_doc: {active_doc}\n"
        f"updated_at: {now}\n"
        f"---\n"
    )
    path.write_text(content, encoding="utf-8")


def next_doc_round(path: Path) -> int:
    """Return next document round: 1 if absent, else current active_doc + 1."""
    if not path.exists():
        return 1
    try:
        raw = read_md_field(path, "active_doc", default="0")
        return int(raw or "0") + 1
    except ValueError:
        return 1


def bump_active_doc(
    cycle_id: str,
    project_root: Path,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> int:
    """Compute next active_doc, persist it, and return the new round."""
    path = resolve_path(cycle_id, project_root, profile_id)
    active_doc = next_doc_round(path)
    save_active_doc(path, active_doc)
    return active_doc


def _cli() -> int:
    parser = argparse.ArgumentParser(description="compose stage session-state.md schema utilities")
    parser.add_argument("--schema", action="store_true", help="Print JSON schema array and exit")
    parser.add_argument("--read", action="store_true", help="Print active_doc")
    parser.add_argument("--next", action="store_true", help="Compute, write, and print next doc round")
    parser.add_argument("--cycle-id", type=str, help="Cycle ID (with --project-root)")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Project root directory")
    parser.add_argument(
        "--profile",
        default=DEFAULT_COMPOSE_PROFILE_ID,
        help="Compose profile id (default: tech-plan)",
    )
    parser.add_argument("--path", type=Path, help="Path to session-state.md")
    args = parser.parse_args()
    profile_id = args.profile.strip() or DEFAULT_COMPOSE_PROFILE_ID

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    if args.read:
        if args.cycle_id:
            if not args.cycle_id.strip():
                parser.error("--cycle-id must not be empty")
            print(load_active_doc_from_cycle(
                args.cycle_id.strip(),
                args.project_root.resolve(),
                profile_id=profile_id,
            ))
            return 0
        if args.path:
            print(load_active_doc(args.path))
            return 0
        parser.error("--read requires --cycle-id or --path")

    if args.next:
        if args.cycle_id:
            if not args.cycle_id.strip():
                parser.error("--cycle-id must not be empty")
            active_doc = bump_active_doc(
                args.cycle_id.strip(),
                args.project_root.resolve(),
                profile_id=profile_id,
            )
            print(active_doc)
            return 0
        if args.path:
            active_doc = next_doc_round(args.path)
            save_active_doc(args.path, active_doc)
            print(active_doc)
            return 0
        parser.error("--next requires --cycle-id or --path")

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
