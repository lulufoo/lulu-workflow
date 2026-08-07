#!/usr/bin/env python3
"""Schema/I/O for ``_topic-focus.json`` (archive-9.0 T2/T3).

Process how: docs/domain/archive/compose/archive-9.0/
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOPIC_FOCUS_BASENAME = "_topic-focus.json"
_PHASES = frozenset({None, "define", "discuss", "summarize"})
_PHASE_STR = frozenset({"define", "discuss", "summarize"})


def topic_focus_path(revision_or_slice_dir: Path) -> Path:
    return Path(revision_or_slice_dir) / TOPIC_FOCUS_BASENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_topic_focus() -> dict[str, Any]:
    return {
        "version": "1",
        "focus": None,
        "phase": None,
        "updated_at": _now_iso(),
    }


def validate_topic_focus(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["topic_focus root must be an object"]
    if str(data.get("version", "")).strip() != "1":
        errors.append("topic_focus.version must be '1'")
    focus = data.get("focus")
    if focus is not None and not str(focus).strip():
        errors.append("topic_focus.focus must be null or non-empty string")
    phase = data.get("phase")
    if phase is not None and str(phase).strip() not in _PHASE_STR:
        errors.append("topic_focus.phase must be null|define|discuss|summarize")
    if focus is None and phase is not None:
        errors.append("topic_focus.phase must be null when focus is null")
    return errors


def normalize_topic_focus(data: dict[str, Any]) -> dict[str, Any]:
    focus = data.get("focus")
    focus_out = None if focus is None else str(focus).strip() or None
    phase = data.get("phase")
    phase_out = None if phase is None else str(phase).strip() or None
    if focus_out is None:
        phase_out = None
    return {
        "version": "1",
        "focus": focus_out,
        "phase": phase_out,
        "updated_at": str(data.get("updated_at") or _now_iso()),
    }


def load_topic_focus(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_topic_focus()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid topic_focus JSON: {exc}") from exc
    errors = validate_topic_focus(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_topic_focus(data)


def save_topic_focus(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_topic_focus(data if isinstance(data, dict) else {})
    normalized["updated_at"] = _now_iso()
    errors = validate_topic_focus(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized
