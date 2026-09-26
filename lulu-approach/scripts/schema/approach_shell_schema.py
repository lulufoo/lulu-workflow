#!/usr/bin/env python3
"""Outer approach shell pointer/state.

On-disk ``discussion-pointer.json`` at the approach root::

    {
      "version": 1,
      "macro_state": "Session"|"PackageReady"|"Reopen"
    }

The decision session is the approach root. There is no nested session node.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SHELL_FILENAME = "discussion-pointer.json"
SHELL_VERSION = 1
MACRO_STATES = frozenset({"Session", "PackageReady", "Reopen"})
_ON_DISK_KEYS = frozenset({"version", "macro_state"})


def shell_path(approach_root: Path) -> Path:
    return Path(approach_root).resolve() / SHELL_FILENAME


def build_shell(
    *,
    macro_state: str = "Session",
    version: int = SHELL_VERSION,
) -> dict[str, Any]:
    return {
        "version": int(version),
        "macro_state": str(macro_state).strip(),
    }


def initial_shell() -> dict[str, Any]:
    """Approach start: the decision session is open."""
    return build_shell(macro_state="Session")


def validate_shell(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["shell must be an object"]

    extra = set(data) - _ON_DISK_KEYS
    if extra:
        errors.append(f"unexpected keys: {sorted(extra)}")

    if data.get("version") != SHELL_VERSION:
        errors.append(f"version must be {SHELL_VERSION}")

    macro = data.get("macro_state")
    if macro not in MACRO_STATES:
        errors.append(
            f"macro_state must be one of {sorted(MACRO_STATES)}, got {macro!r}"
        )

    return errors


def save_shell(approach_root: Path, shell: dict[str, Any]) -> Path:
    errors = validate_shell(shell)
    if errors:
        raise ValueError("; ".join(errors))
    path = shell_path(approach_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": int(shell["version"]),
        "macro_state": str(shell["macro_state"]).strip(),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_shell(approach_root: Path) -> dict[str, Any]:
    path = shell_path(approach_root)
    if not path.is_file():
        raise FileNotFoundError(f"missing approach shell: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_shell(data)
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "version": int(data["version"]),
        "macro_state": str(data["macro_state"]).strip(),
    }
