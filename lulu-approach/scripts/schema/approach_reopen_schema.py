#!/usr/bin/env python3
"""Schema and atomic I/O for approach reopen transactions."""

from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path
from typing import Any

_DECISION_SCRIPTS = Path(__file__).resolve().parents[3] / "decision" / "scripts"
if str(_DECISION_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DECISION_SCRIPTS))

from dec_io import atomic_write_text  # noqa: E402

REOPEN_FILENAME = "reopen.json"
REOPEN_VERSION = "1"
REOPEN_STATES = frozenset({"preparing", "reopen_pending", "repaired", "failed"})
TERMINAL_STATES = frozenset({"repaired", "failed"})
_ON_DISK_KEYS = frozenset(
    {"version", "transaction_id", "state", "previous"}
)


def reopen_path(approach_root: Path) -> Path:
    """Return the single active reopen transaction path."""
    return Path(approach_root).resolve() / REOPEN_FILENAME


def new_transaction_id() -> str:
    """Return an opaque transaction identifier."""
    return f"reopen-{secrets.token_hex(8)}"


def _text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def build_reopen(
    *,
    transaction_id: str,
    state: str,
    previous: dict[str, Any],
    version: str = REOPEN_VERSION,
) -> dict[str, Any]:
    """Build an unvalidated persisted transaction payload."""
    return {
        "version": str(version).strip(),
        "transaction_id": str(transaction_id).strip(),
        "state": str(state).strip(),
        "previous": {
            "macro_state": str(previous.get("macro_state", "")).strip(),
            "active_session": _text(previous.get("active_session")),
        },
    }


def validate_reopen(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a reopen transaction."""
    if not isinstance(data, dict):
        raise ValueError("reopen must be a JSON object")
    extra = set(data) - _ON_DISK_KEYS
    if extra:
        raise ValueError(f"reopen unexpected keys: {sorted(extra)}")
    version = str(data.get("version", "")).strip()
    if version != REOPEN_VERSION:
        raise ValueError(f"reopen version must be {REOPEN_VERSION!r}, got {version!r}")
    transaction_id = str(data.get("transaction_id", "")).strip()
    if not transaction_id:
        raise ValueError("reopen transaction_id is required")
    state = str(data.get("state", "")).strip()
    if state not in REOPEN_STATES:
        raise ValueError(
            f"reopen state must be one of {sorted(REOPEN_STATES)}, got {state!r}"
        )
    previous = data.get("previous")
    if not isinstance(previous, dict):
        raise ValueError("reopen previous must be an object")
    return build_reopen(
        transaction_id=transaction_id,
        state=state,
        previous=previous,
        version=version,
    )


def save_reopen(approach_root: Path, data: dict[str, Any]) -> Path:
    """Persist a transaction without replacing a different active transaction."""
    payload = validate_reopen(data)
    path = reopen_path(approach_root)
    if path.is_file():
        current = load_reopen(approach_root)
        if (
            current["transaction_id"] != payload["transaction_id"]
            and current["state"] not in TERMINAL_STATES
        ):
            raise ValueError("cannot replace active reopen transaction")
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def load_reopen(approach_root: Path) -> dict[str, Any]:
    """Load the active reopen transaction."""
    path = reopen_path(approach_root)
    if not path.is_file():
        raise FileNotFoundError(f"reopen not found: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    return validate_reopen(raw)


def try_load_reopen(approach_root: Path) -> dict[str, Any] | None:
    """Load a transaction when one exists."""
    path = reopen_path(approach_root)
    return load_reopen(approach_root) if path.is_file() else None
