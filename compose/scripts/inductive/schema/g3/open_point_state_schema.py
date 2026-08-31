#!/usr/bin/env python3
"""Schema and I/O for slice ``open-point-state.json``.

Loop position only: idle|processing plus the active batch/open ids.

Design rationale:
docs/domain/archive/compose/archive-34.0/compose-g3-open-point-loop-refactor-design.md
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parents[3] / "_kernel"
if str(_SECTION) not in sys.path:
    sys.path.insert(0, str(_SECTION))

from compose_state_lock import durable_write_json  # noqa: E402

STATE_BASENAME = "open-point-state.json"
STATE_VERSION = 1
PHASES = frozenset({"idle", "processing"})
_STATE_KEYS = frozenset({"version", "phase", "active_batch_id", "active_open_id"})
_BATCH_ID_RE = re.compile(r"^B-([1-9]\d*)$")
_OPEN_ID_RE = re.compile(r"^O-([1-9]\d*)$")


def open_point_state_path(slice_dir: Path) -> Path:
    return Path(slice_dir) / STATE_BASENAME


def empty_open_point_state() -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "phase": "idle",
        "active_batch_id": None,
        "active_open_id": None,
    }


def _id_or_null(value: Any, pattern: re.Pattern[str], label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, str) or not pattern.match(value.strip()):
        return [f"{label} must be null or match its id form"]
    return []


def validate_open_point_state(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["open-point-state root must be an object"]
    errors: list[str] = []
    extra = set(data) - _STATE_KEYS
    if extra:
        errors.append(f"open-point-state unexpected fields {sorted(extra)}")
    if data.get("version") != STATE_VERSION:
        errors.append("open-point-state.version must be 1")
    phase = data.get("phase")
    if phase not in PHASES:
        errors.append(f"open-point-state.phase invalid: {phase!r}")
    errors.extend(
        _id_or_null(data.get("active_batch_id"), _BATCH_ID_RE, "active_batch_id")
    )
    errors.extend(
        _id_or_null(data.get("active_open_id"), _OPEN_ID_RE, "active_open_id")
    )
    if phase == "idle":
        if data.get("active_batch_id") is not None or data.get("active_open_id") is not None:
            errors.append("idle requires active_batch_id and active_open_id to be null")
    if phase == "processing" and data.get("active_batch_id") is None:
        errors.append("processing requires active_batch_id")
    return errors


def normalize_open_point_state(data: dict[str, Any]) -> dict[str, Any]:
    batch_id = data.get("active_batch_id")
    open_id = data.get("active_open_id")
    return {
        "version": STATE_VERSION,
        "phase": str(data.get("phase", "idle")).strip().lower(),
        "active_batch_id": None if batch_id is None else str(batch_id).strip(),
        "active_open_id": None if open_id is None else str(open_id).strip(),
    }


def load_open_point_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_open_point_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid open-point-state JSON: {exc}") from exc
    errors = validate_open_point_state(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_open_point_state(data)


def save_open_point_state(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    errors = validate_open_point_state(data)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = normalize_open_point_state(data)
    errors = validate_open_point_state(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    durable_write_json(path, normalized)
    return normalized
