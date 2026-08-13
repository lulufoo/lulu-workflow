#!/usr/bin/env python3
"""Schema and I/O for revision ``split-intake.json``.

Eight-slot v1 minimum set. Empty slot (missing or blank) without explicit
``N/A`` blocks complete status.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SPLIT_INTAKE_FILENAME = "split-intake.json"
SPLIT_INTAKE_VERSION = 1
_VALID_STATUS = frozenset({"draft", "complete"})

INTAKE_SLOT_KEYS = (
    "package_boundary",
    "cut_axis_preference",
    "modules",
    "deps_order",
    "plan_autonomy",
    "seam_ownership",
    "non_goals",
    "split_risks",
)


def split_intake_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / SPLIT_INTAKE_FILENAME


def empty_intake(*, status: str = "draft") -> dict[str, Any]:
    slots = {k: "" for k in INTAKE_SLOT_KEYS}
    return {
        "version": SPLIT_INTAKE_VERSION,
        "status": status,
        "slots": slots,
        "override_reason": "",
    }


def _slot_filled(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    return bool(text)


def validate_split_intake(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["split-intake must be an object"]
    if data.get("version") != SPLIT_INTAKE_VERSION:
        errors.append(f"version must be {SPLIT_INTAKE_VERSION}")
    status = data.get("status")
    if status not in _VALID_STATUS:
        errors.append("status must be draft|complete")
    slots = data.get("slots")
    if not isinstance(slots, dict):
        errors.append("slots must be an object")
        return errors
    for key in INTAKE_SLOT_KEYS:
        if key not in slots:
            errors.append(f"slots missing {key}")
            continue
        if status == "complete" and not _slot_filled(slots.get(key)):
            errors.append(f"slots.{key} must be filled or N/A for complete")
    extra = set(slots) - set(INTAKE_SLOT_KEYS)
    if extra:
        errors.append(f"slots unexpected keys: {sorted(extra)}")
    return errors


def save_split_intake(revision_dir: Path, data: dict[str, Any]) -> Path:
    errors = validate_split_intake(data)
    if errors:
        raise ValueError("; ".join(errors))
    path = split_intake_path(revision_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_split_intake(revision_dir: Path) -> dict[str, Any]:
    path = split_intake_path(revision_dir)
    if not path.is_file():
        raise FileNotFoundError(f"missing split intake: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_split_intake(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data
