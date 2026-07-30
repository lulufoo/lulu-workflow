#!/usr/bin/env python3
"""Outer approach shell pointer/state (archive-1.0 P2.shell).

On-disk ``discussion-pointer.json`` at the approach root::

    {
      "version": 1,
      "macro_state": "Main"|"Split"|"Working"|"PackageReady"|"MainReopen"|"SplitReopen",
      "focus": null|"main"|"D1"|...,
      "by_id": {
        "D1": {"phase": "pending"|"in_progress", "delivered": bool, "frozen": bool},
        ...
      },
      "split_delivered": bool
    }

``split_delivered`` stubs Split-phase completion until P2.split owns the cut.
Ready sets are computed, not persisted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SHELL_FILENAME = "discussion-pointer.json"
SHELL_VERSION = 1
MACRO_STATES = frozenset(
    {"Main", "Split", "Working", "PackageReady", "MainReopen", "SplitReopen"}
)
NODE_PHASES = frozenset({"pending", "in_progress"})
_ON_DISK_KEYS = frozenset(
    {"version", "macro_state", "focus", "by_id", "split_delivered"}
)
_CELL_KEYS = frozenset({"phase", "delivered", "frozen"})
_DX_ID_RE = re.compile(r"^D\d+$")
_FOCUS_RE = re.compile(r"^(main|D\d+)$")


def shell_path(approach_root: Path) -> Path:
    return Path(approach_root).resolve() / SHELL_FILENAME


def empty_cell(*, phase: str = "pending") -> dict[str, Any]:
    if phase not in NODE_PHASES:
        raise ValueError(f"phase must be pending|in_progress, got {phase!r}")
    return {"phase": phase, "delivered": False, "frozen": False}


def build_shell(
    *,
    macro_state: str = "Main",
    focus: str | None = None,
    by_id: dict[str, dict[str, Any]] | None = None,
    split_delivered: bool = False,
    version: int = SHELL_VERSION,
) -> dict[str, Any]:
    return {
        "version": int(version),
        "macro_state": str(macro_state).strip(),
        "focus": None if focus is None else str(focus).strip(),
        "by_id": {k: dict(v) for k, v in (by_id or {}).items()},
        "split_delivered": bool(split_delivered),
    }


def initial_shell() -> dict[str, Any]:
    """Approach start: Main, no focus, empty by_id."""
    return build_shell(
        macro_state="Main",
        focus=None,
        by_id={},
        split_delivered=False,
    )


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

    focus = data.get("focus")
    if focus is not None:
        focus_s = str(focus).strip()
        if not _FOCUS_RE.match(focus_s):
            errors.append(f"focus must be main|D<number> or null, got {focus!r}")
        focus = focus_s
    else:
        focus = None

    if not isinstance(data.get("split_delivered"), bool):
        errors.append("split_delivered must be a boolean")

    by_id = data.get("by_id")
    if not isinstance(by_id, dict):
        errors.append("by_id must be an object")
        return errors

    for nid, cell in by_id.items():
        where = f"by_id[{nid}]"
        if not _DX_ID_RE.match(str(nid)):
            errors.append(f"{where}: id must match D<number>")
        if not isinstance(cell, dict):
            errors.append(f"{where} must be an object")
            continue
        extra_cell = set(cell) - _CELL_KEYS
        if extra_cell:
            errors.append(f"{where} unexpected keys: {sorted(extra_cell)}")
        if cell.get("phase") not in NODE_PHASES:
            errors.append(f"{where}.phase must be pending|in_progress")
        if not isinstance(cell.get("delivered"), bool):
            errors.append(f"{where}.delivered must be a boolean")
        if not isinstance(cell.get("frozen"), bool):
            errors.append(f"{where}.frozen must be a boolean")

    if macro == "Working":
        if focus is None:
            errors.append("Working requires a focus node_id")
        elif focus == "main":
            errors.append("Working focus must be a Dx node_id")
        elif focus not in by_id:
            errors.append(f"focus {focus!r} missing from by_id")
        if not by_id:
            errors.append("Working requires non-empty by_id")
    elif macro in {"Main", "Split"} and focus is not None and focus != "main":
        errors.append(f"{macro} focus must be null or main")
    elif macro in {"MainReopen", "SplitReopen"} and focus != "main":
        errors.append(f"{macro} focus must be main")

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
        "focus": None if shell.get("focus") is None else str(shell["focus"]).strip(),
        "by_id": shell.get("by_id") or {},
        "split_delivered": bool(shell.get("split_delivered", False)),
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
        "focus": None if data.get("focus") is None else str(data["focus"]).strip(),
        "by_id": dict(data.get("by_id") or {}),
        "split_delivered": bool(data.get("split_delivered", False)),
    }
