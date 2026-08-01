#!/usr/bin/env python3
"""Schema and I/O for decision session-state.md."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dec_io import atomic_write_text

SESSION_STATE_FILENAME = "session-state.md"

# First-class session states (P1.4′ Frozen).
# Node/session terminal is Completed (not stage Delivered).
SESSION_STATES = frozenset({"InProgress", "Frozen", "Completed", "Invalidated"})

# Legacy on-disk value accepted on read; new writes use Completed only.
_LEGACY_TERMINAL = "Delivered"
_READ_STATES = SESSION_STATES | {_LEGACY_TERMINAL}

# States from which $DEC_REOPEN may enter Frozen.
REOPEN_SOURCE_STATES = frozenset({"Completed", "InProgress", _LEGACY_TERMINAL})


def session_state_file(session_dir: Path) -> Path:
    return session_dir / SESSION_STATE_FILENAME


def normalize_session_state(state: str) -> str:
    """Map legacy Delivered → Completed for in-memory use."""
    current = str(state).strip()
    if current == _LEGACY_TERMINAL:
        return "Completed"
    return current


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    block = text[3:end]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line == "---" or ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def load_session_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"session-state not found: {path}")
    fields = _parse_frontmatter(path.read_text(encoding="utf-8"))
    current = str(fields.get("current_state", "")).strip()
    if current not in _READ_STATES:
        raise ValueError(f"invalid current_state: {current!r}")
    return {
        "version": str(fields.get("version", "1")).strip() or "1",
        "current_state": normalize_session_state(current),
        "updated_at": str(fields.get("updated_at", "")).strip(),
    }


def read_current_state(path: Path) -> str:
    return str(load_session_state(path)["current_state"])


def write_session_state(path: Path, current_state: str) -> None:
    normalized = normalize_session_state(current_state)
    if normalized not in SESSION_STATES:
        raise ValueError(f"invalid current_state: {current_state!r}")
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    content = (
        f"---\n"
        f"version: 1\n"
        f"current_state: {normalized}\n"
        f"updated_at: {now}\n"
        f"---\n"
    )
    atomic_write_text(path, content)


def set_session_frozen(session_dir: Path) -> str:
    """Transition Completed/InProgress → Frozen. Returns prior state."""
    path = session_state_file(session_dir)
    prior = read_current_state(path)
    if prior not in frozenset({"Completed", "InProgress"}):
        raise ValueError(
            f"reopen requires current_state in ['Completed', 'InProgress'], got {prior!r}"
        )
    write_session_state(path, "Frozen")
    return prior


def unfreeze_session(session_dir: Path) -> bool:
    """If Frozen, set InProgress. Returns True when a transition happened."""
    path = session_state_file(session_dir)
    if not path.exists():
        return False
    if read_current_state(path) != "Frozen":
        return False
    write_session_state(path, "InProgress")
    return True
