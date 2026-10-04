#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for compose stage session-state.md (v2).

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
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_here = Path(__file__).resolve().parent
for _parent in [_here, *_here.parents]:
    _scripts = _parent if (_parent / "project_root.py").is_file() else _parent / "scripts"
    if (_scripts / "project_root.py").is_file():
        if str(_scripts) not in sys.path:
            sys.path.insert(0, str(_scripts))
        break
from project_root import apply_project_root_arg  # noqa: E402

from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[2]
_KERNEL = _SCRIPTS / "_kernel"
for _p in (_KERNEL,):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from compose_state_lock import durable_write_text
from workflow_common import read_md_field
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID
from workflow_profile_paths import session_state_path

SESSION_STATE_VERSION = 2
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_SCHEMA: list[dict] = [
    {"field": "version", "type": "int", "required": True,
     "description": "Schema version (currently 2)"},
    {"field": "active_doc", "type": "int", "required": True,
     "description": "Active revision number (maps to revision{N}/)"},
    {"field": "profile_path", "type": "string", "required": True,
     "description": "Absolute path to revision-local runtime-profile.json"},
    {"field": "profile_digest", "type": "string", "required": True,
     "description": "SHA-256 of runtime-profile.json bytes"},
    {"field": "start_id", "type": "string", "required": True,
     "description": "Start identity UUID"},
    {"field": "holder_finalized", "type": "bool", "required": True,
     "description": "Holder finalize handshake complete"},
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
    return project_root / session_state_path(cycle_id, profile_id, project_root)


def _parse_bool(raw: str) -> bool:
    text = str(raw).strip().lower()
    if text in {"true", "yes", "1"}:
        return True
    if text in {"false", "no", "0"}:
        return False
    raise ValueError(f"holder_finalized must be boolean, got {raw!r}")


def validate_session_state(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["session-state must be an object"]
    if data.get("version") != SESSION_STATE_VERSION:
        errors.append(f"version must be {SESSION_STATE_VERSION}")
    active_doc = data.get("active_doc")
    if not isinstance(active_doc, int) or isinstance(active_doc, bool) or active_doc < 1:
        errors.append("active_doc must be a positive integer")
    profile_path = str(data.get("profile_path") or "").strip()
    if not profile_path:
        errors.append("profile_path must be non-empty")
    digest = str(data.get("profile_digest") or "").strip()
    if not _DIGEST_RE.fullmatch(digest):
        errors.append("profile_digest must be 64 lowercase hex characters")
    start_id = str(data.get("start_id") or "").strip()
    if not start_id:
        errors.append("start_id must be non-empty")
    if not isinstance(data.get("holder_finalized"), bool):
        errors.append("holder_finalized must be a boolean")
    return errors


def load_session_state(path: Path) -> dict[str, Any]:
    """Load and validate session-state.md v2."""
    if not path.exists():
        raise ValueError(f"session-state.md not found: {path}")
    version_raw = read_md_field(path, "version", default="")
    try:
        version = int(version_raw)
    except ValueError as exc:
        raise ValueError(f"invalid session-state version in {path}") from exc
    if version != SESSION_STATE_VERSION:
        raise ValueError(
            f"unsupported session-state version {version} in {path}; open a new revision"
        )
    raw_doc = read_md_field(path, "active_doc", default="")
    try:
        active_doc = int(raw_doc)
    except ValueError as exc:
        raise ValueError(f"active_doc must be an integer in {path}") from exc
    payload = {
        "version": SESSION_STATE_VERSION,
        "active_doc": active_doc,
        "profile_path": read_md_field(path, "profile_path", default="").strip(),
        "profile_digest": read_md_field(path, "profile_digest", default="").strip(),
        "start_id": read_md_field(path, "start_id", default="").strip(),
        "holder_finalized": _parse_bool(read_md_field(path, "holder_finalized", default="")),
        "updated_at": read_md_field(path, "updated_at", default=""),
    }
    errors = validate_session_state(payload)
    if errors:
        raise ValueError("; ".join(errors))
    return payload


def save_session_state(
    path: Path,
    *,
    active_doc: int,
    profile_path: str,
    profile_digest: str,
    start_id: str,
    holder_finalized: bool,
) -> None:
    """Durable-write session-state.md v2. This is the revision/profile commit point."""
    payload = {
        "version": SESSION_STATE_VERSION,
        "active_doc": int(active_doc),
        "profile_path": str(profile_path).strip(),
        "profile_digest": str(profile_digest).strip().lower(),
        "start_id": str(start_id).strip(),
        "holder_finalized": bool(holder_finalized),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    errors = validate_session_state(payload)
    if errors:
        raise ValueError("; ".join(errors))
    finalized = "true" if payload["holder_finalized"] else "false"
    content = (
        f"---\n"
        f"version: {SESSION_STATE_VERSION}\n"
        f"active_doc: {payload['active_doc']}\n"
        f"profile_path: {payload['profile_path']}\n"
        f"profile_digest: {payload['profile_digest']}\n"
        f"start_id: {payload['start_id']}\n"
        f"holder_finalized: {finalized}\n"
        f"updated_at: {payload['updated_at']}\n"
        f"---\n"
    )
    durable_write_text(path, content)


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
    """Persist active_doc, preserving other v2 fields when present."""
    profile_path = "unbound"
    profile_digest = "0" * 64
    start_id = "test"
    holder_finalized = True
    if path.exists():
        try:
            existing = load_session_state(path)
            profile_path = str(existing["profile_path"])
            profile_digest = str(existing["profile_digest"])
            start_id = str(existing["start_id"])
            holder_finalized = bool(existing["holder_finalized"])
        except ValueError:
            pass
    save_session_state(
        path,
        active_doc=active_doc,
        profile_path=profile_path,
        profile_digest=profile_digest,
        start_id=start_id,
        holder_finalized=holder_finalized,
    )


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
        help="Compose profile id (default: lulu-plan)",
    )
    parser.add_argument("--path", type=Path, help="Path to session-state.md")
    args = parser.parse_args()
    apply_project_root_arg(args)
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
