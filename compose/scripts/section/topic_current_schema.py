#!/usr/bin/env python3
"""Schema/I/O for ``_topic-current.json`` (archive-10.0 T1).

Persists the current topic as part of **adopt**. Does not store dialogue text
or What-phase ordering. Not a topic tree. Gap-state topics are not stored here.

Process how: docs/domain/archive/compose/archive-10.0/
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOPIC_CURRENT_BASENAME = "_topic-current.json"


def topic_current_path(revision_or_slice_dir: Path) -> Path:
    return Path(revision_or_slice_dir) / TOPIC_CURRENT_BASENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_topic_current() -> dict[str, Any]:
    return {
        "version": "1",
        "title": None,
        "scope": None,
        "clarified": False,
        "human_adopted": False,
        "conclusion": None,
        "conclusion_confirmed": False,
        "updated_at": _now_iso(),
    }


def validate_topic_current(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["topic_current root must be an object"]
    if str(data.get("version", "")).strip() != "1":
        errors.append("topic_current.version must be '1'")
    title = data.get("title")
    scope = data.get("scope")
    clarified = bool(data.get("clarified"))
    human_adopted = bool(data.get("human_adopted"))
    conclusion = data.get("conclusion")
    confirmed = bool(data.get("conclusion_confirmed"))
    if title is not None and not str(title).strip():
        errors.append("topic_current.title must be null or non-empty string")
    if scope is not None and not str(scope).strip():
        errors.append("topic_current.scope must be null or non-empty string")
    if clarified:
        if not (isinstance(title, str) and title.strip()):
            errors.append("topic_current.clarified requires non-empty title")
        if not (isinstance(scope, str) and scope.strip()):
            errors.append("topic_current.clarified requires non-empty scope")
        if not human_adopted:
            errors.append("topic_current.clarified requires human_adopted=true")
    if confirmed:
        if not (isinstance(conclusion, str) and conclusion.strip()):
            errors.append(
                "topic_current.conclusion_confirmed requires non-empty conclusion",
            )
        if not clarified:
            errors.append(
                "topic_current.conclusion_confirmed requires clarified topic",
            )
    return errors


def normalize_topic_current(data: dict[str, Any]) -> dict[str, Any]:
    title = data.get("title")
    scope = data.get("scope")
    conclusion = data.get("conclusion")
    return {
        "version": "1",
        "title": None if title is None else (str(title).strip() or None),
        "scope": None if scope is None else (str(scope).strip() or None),
        "clarified": bool(data.get("clarified")),
        "human_adopted": bool(data.get("human_adopted")),
        "conclusion": (
            None if conclusion is None else (str(conclusion).strip() or None)
        ),
        "conclusion_confirmed": bool(data.get("conclusion_confirmed")),
        "updated_at": str(data.get("updated_at") or _now_iso()),
    }


def load_topic_current(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_topic_current()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid topic_current JSON: {exc}") from exc
    errors = validate_topic_current(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_topic_current(data)


def save_topic_current(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_topic_current(data if isinstance(data, dict) else {})
    normalized["updated_at"] = _now_iso()
    errors = validate_topic_current(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized


def has_unconfirmed_conclusion(data: dict[str, Any]) -> bool:
    """True when a conclusion text exists but human has not confirmed."""
    conclusion = data.get("conclusion")
    if not (isinstance(conclusion, str) and conclusion.strip()):
        return False
    return not bool(data.get("conclusion_confirmed"))
