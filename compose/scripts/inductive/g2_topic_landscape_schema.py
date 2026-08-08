#!/usr/bin/env python3
"""Schema/I/O for ``_topic-landscape.json`` (archive-21.0).

Single-slot (MVP): each record overwrites the previous run and issues a new
``run_id``. Written only via inductive gate ``record-topic-landscape``.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOPIC_LANDSCAPE_BASENAME = "_topic-landscape.json"
LANDSCAPE_PURPOSES = frozenset({"seek", "refresh", "pre_close"})


def topic_landscape_path(revision_or_slice_dir: Path) -> Path:
    return Path(revision_or_slice_dir) / TOPIC_LANDSCAPE_BASENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id() -> str:
    return uuid.uuid4().hex


def validate_topic_landscape(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["topic_landscape root must be an object"]
    if str(data.get("version", "")).strip() != "1":
        errors.append("topic_landscape.version must be '1'")
    run_id = data.get("run_id")
    if not (isinstance(run_id, str) and run_id.strip()):
        errors.append("topic_landscape.run_id must be a non-empty string")
    purpose = data.get("purpose")
    if purpose not in LANDSCAPE_PURPOSES:
        errors.append(
            "topic_landscape.purpose must be one of "
            + ", ".join(sorted(LANDSCAPE_PURPOSES)),
        )
    gap = data.get("gap_remaining")
    if not isinstance(gap, int) or isinstance(gap, bool) or gap < 0:
        errors.append("topic_landscape.gap_remaining must be a non-negative int")
    summary = data.get("summary")
    if summary is not None and not isinstance(summary, str):
        errors.append("topic_landscape.summary must be null or string")
    return errors


def normalize_topic_landscape(data: dict[str, Any]) -> dict[str, Any]:
    summary = data.get("summary")
    return {
        "version": "1",
        "run_id": str(data.get("run_id") or "").strip(),
        "purpose": str(data.get("purpose") or "").strip(),
        "gap_remaining": int(data.get("gap_remaining") or 0),
        "summary": None if summary is None else str(summary),
        "recorded_at": str(data.get("recorded_at") or _now_iso()),
    }


def load_topic_landscape(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid topic_landscape JSON: {exc}") from exc
    errors = validate_topic_landscape(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_topic_landscape(data)


def save_topic_landscape(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_topic_landscape(data if isinstance(data, dict) else {})
    normalized["recorded_at"] = _now_iso()
    errors = validate_topic_landscape(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized
