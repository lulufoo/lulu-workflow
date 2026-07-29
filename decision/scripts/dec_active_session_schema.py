#!/usr/bin/env python3
"""Schema and I/O for active-session.json (archive-1.1 Active Session)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dec_io import atomic_write_text

ACTIVE_SESSION_FILENAME = "active-session.json"
_SESSION_DIR_RE = re.compile(r"^(main|D\d+|\.)$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def active_session_path(stage_outer: Path) -> Path:
    return Path(stage_outer) / ACTIVE_SESSION_FILENAME


def validate_active_session(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("active-session must be a JSON object")
    version = str(data.get("version", "")).strip()
    if version != "1":
        raise ValueError(f"active-session version must be '1', got {version!r}")
    session_dir = str(data.get("session_dir", "")).strip()
    if not _SESSION_DIR_RE.match(session_dir):
        raise ValueError(
            f"session_dir must be main|D<number>|., got {session_dir!r}"
        )
    updated_at = str(data.get("updated_at", "")).strip()
    if not updated_at:
        raise ValueError("updated_at is required")
    return {
        "version": "1",
        "session_dir": session_dir,
        "updated_at": updated_at,
    }


def load_active_session(stage_outer: Path) -> dict[str, Any]:
    path = active_session_path(stage_outer)
    if not path.is_file():
        raise FileNotFoundError(f"active-session not found: {path}")
    import json

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("active-session must be a JSON object")
    return validate_active_session(raw)


def save_active_session(stage_outer: Path, session_dir: str) -> dict[str, Any]:
    """Write active-session.json under stage outer root."""
    payload = validate_active_session(
        {
            "version": "1",
            "session_dir": str(session_dir).strip(),
            "updated_at": _now_iso(),
        }
    )
    outer = Path(stage_outer)
    outer.mkdir(parents=True, exist_ok=True)
    import json

    atomic_write_text(
        active_session_path(outer),
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    return payload


def is_valid_session_root(session_dir: Path) -> bool:
    base = Path(session_dir)
    return base.is_dir() and (
        (base / "gate-state.json").is_file()
        or (base / "domain-constraints.json").is_file()
    )


def relative_session_dir_for(stage_outer: Path, session_abs: Path) -> str:
    """Map absolute session root to relative session_dir under stage outer."""
    outer = Path(stage_outer).resolve()
    target = Path(session_abs).resolve()
    if target == outer:
        return "."
    try:
        rel = target.relative_to(outer)
    except ValueError as exc:
        raise ValueError(
            f"session_dir {target} is not under stage outer {outer}"
        ) from exc
    if len(rel.parts) != 1:
        raise ValueError(
            f"session_dir must be a single segment under outer, got {rel.as_posix()!r}"
        )
    name = rel.parts[0]
    if not _SESSION_DIR_RE.match(name):
        raise ValueError(f"invalid nested session name: {name!r}")
    return name
