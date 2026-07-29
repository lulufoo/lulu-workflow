#!/usr/bin/env python3
"""Cycle-level delivered-refs.json I/O (shared Layer A)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from platform_schema import detect_platform
from platforms.paths import cache_dir

_FILE_NAME = "delivered-refs.json"
_VERSION = 1


def _cache_dir() -> Path:
    return cache_dir(detect_platform())


def delivered_refs_file_path(cycle_id: str, project_root: Path) -> Path:
    return (project_root / _cache_dir() / cycle_id / _FILE_NAME).resolve()


def _empty_file_payload() -> dict[str, Any]:
    return {"version": _VERSION, "entries": {}}


def load_delivered_refs_file(cycle_id: str, project_root: Path) -> dict[str, Any]:
    path = delivered_refs_file_path(cycle_id, project_root)
    if not path.is_file():
        return _empty_file_payload()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"invalid delivered-refs.json (not object): {path}")
    entries = data.get("entries")
    if entries is None:
        data["entries"] = {}
    elif not isinstance(entries, dict):
        raise ValueError(f"invalid delivered-refs.json entries: {path}")
    return data


def save_delivered_refs_file(cycle_id: str, project_root: Path, data: dict[str, Any]) -> Path:
    path = delivered_refs_file_path(cycle_id, project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["version"] = _VERSION
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def record_delivered_ref(
    cycle_id: str,
    project_root: Path,
    *,
    delivered_type: str,
    path: str,
    revision: int | str,
    profile_id: str,
    source_workflow_state: str,
    decision_fact_path: str | None = None,
    artifact: str | None = None,
) -> None:
    """Upsert one stage entry in {cycle_id}/delivered-refs.json.

    Optional ``decision_fact_path`` registers decision-fact.json beside decision-doc.
    Optional ``artifact`` marks delivery shape (e.g. ``decision-package``, P0.7).
    Legacy parallel key ``{stage}-facts`` is dropped when present.
    Compose does not register upstream ``_facts.json`` on the entry.
    """
    dtype = delivered_type.strip()
    if not dtype:
        raise ValueError("delivered_type must be non-empty")
    data = load_delivered_refs_file(cycle_id, project_root)
    entries = dict(data.get("entries") or {})
    entry: dict[str, Any] = {
        "delivered_type": dtype,
        "path": str(Path(path).resolve()),
        "revision": revision,
        "profile_id": profile_id,
        "delivered_at": datetime.now(timezone.utc).isoformat(),
        "source_workflow_state": source_workflow_state,
    }
    if decision_fact_path is not None and str(decision_fact_path).strip():
        entry["decision_fact_path"] = str(Path(decision_fact_path).resolve())
    if artifact is not None and str(artifact).strip():
        entry["artifact"] = str(artifact).strip()
    entries[dtype] = entry
    entries.pop(f"{dtype}-facts", None)
    data["entries"] = entries
    save_delivered_refs_file(cycle_id, project_root, data)
