#!/usr/bin/env python3
"""Schema/I/O for ``_g2-topic-exit.json`` (archive-21.0).

Exit receipt references a ``topic-landscape`` ``run_id``. Written only via
inductive gate ``record-g2-topic-exit``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

G2_TOPIC_EXIT_BASENAME = "_g2-topic-exit.json"
EXIT_RESULTS = frozenset({"cleared", "hard_skip"})


def g2_topic_exit_path(revision_or_slice_dir: Path) -> Path:
    return Path(revision_or_slice_dir) / G2_TOPIC_EXIT_BASENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_g2_topic_exit(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["g2_topic_exit root must be an object"]
    if str(data.get("version", "")).strip() != "1":
        errors.append("g2_topic_exit.version must be '1'")
    run_id = data.get("landscape_run_id")
    if not (isinstance(run_id, str) and run_id.strip()):
        errors.append("g2_topic_exit.landscape_run_id must be a non-empty string")
    result = data.get("result")
    if result not in EXIT_RESULTS:
        errors.append(
            "g2_topic_exit.result must be one of "
            + ", ".join(sorted(EXIT_RESULTS)),
        )
    gap = data.get("gap_remaining")
    if not isinstance(gap, int) or isinstance(gap, bool) or gap < 0:
        errors.append("g2_topic_exit.gap_remaining must be a non-negative int")
    if data.get("human_confirmed") is not True:
        errors.append("g2_topic_exit.human_confirmed must be true")
    if data.get("purpose") != "pre_close":
        errors.append("g2_topic_exit.purpose must be 'pre_close'")
    return errors


def normalize_g2_topic_exit(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "1",
        "landscape_run_id": str(data.get("landscape_run_id") or "").strip(),
        "result": str(data.get("result") or "").strip(),
        "gap_remaining": int(data.get("gap_remaining") or 0),
        "human_confirmed": bool(data.get("human_confirmed")),
        "purpose": "pre_close",
        "recorded_at": str(data.get("recorded_at") or _now_iso()),
    }


def load_g2_topic_exit(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid g2_topic_exit JSON: {exc}") from exc
    errors = validate_g2_topic_exit(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_g2_topic_exit(data)


def save_g2_topic_exit(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_g2_topic_exit(data if isinstance(data, dict) else {})
    normalized["recorded_at"] = _now_iso()
    errors = validate_g2_topic_exit(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized
