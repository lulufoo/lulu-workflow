#!/usr/bin/env python3
"""Decision-oriented split intake (archive-1.0 P2.split S1=B).

Six-slot minimal set at approach root ``split-intake.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SPLIT_INTAKE_FILENAME = "split-intake.json"
SPLIT_INTAKE_VERSION = 1
_VALID_STATUS = frozenset({"draft", "complete"})

# 切分目标、候选结构面、依赖／顺序、每片可独立交付判据、非目标、风险
INTAKE_SLOT_KEYS = (
    "split_goal",
    "candidate_structure_faces",
    "deps_order",
    "slice_autonomy",
    "non_goals",
    "split_risks",
)


def split_intake_path(approach_root: Path) -> Path:
    return Path(approach_root).resolve() / SPLIT_INTAKE_FILENAME


def empty_intake(*, status: str = "draft") -> dict[str, Any]:
    return {
        "version": SPLIT_INTAKE_VERSION,
        "status": status,
        "slots": {k: "" for k in INTAKE_SLOT_KEYS},
        "override_reason": "",
        "recommend_split": None,
    }


def _slot_filled(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


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
    rec = data.get("recommend_split")
    if rec is not None and not isinstance(rec, bool):
        errors.append("recommend_split must be bool or null")
    if "override_reason" in data and not isinstance(data["override_reason"], str):
        errors.append("override_reason must be a string")
    return errors


def save_split_intake(approach_root: Path, data: dict[str, Any]) -> Path:
    errors = validate_split_intake(data)
    if errors:
        raise ValueError("; ".join(errors))
    path = split_intake_path(approach_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_split_intake(approach_root: Path) -> dict[str, Any]:
    path = split_intake_path(approach_root)
    if not path.is_file():
        raise FileNotFoundError(f"missing split intake: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_split_intake(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data
