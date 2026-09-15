#!/usr/bin/env python3
"""Schema and I/O for revision ``_chapter-write-state.json`` (archive-5.0).

Serial Writing Write progress per ``chapter_id`` (``{leaf.id}-{lens}``).
Process how: docs/archive/lulu-dev-workflow/compose/archive-5.0/compose-chapter-write-state-design.md
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CHAPTER_WRITE_STATE_BASENAME = "_chapter-write-state.json"
CHAPTER_WRITE_STATE_KIND = "chapter-write-state"
_STATUS_UNIT = frozenset({"pending", "in_progress", "done"})
_STATUS_TOP = frozenset({"pending", "in_progress", "complete"})


def chapter_write_state_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / CHAPTER_WRITE_STATE_BASENAME


def validate_chapter_write_state(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["chapter_write_state root must be an object"]
    if str(data.get("version", "")).strip() != "1":
        errors.append("chapter_write_state.version must be '1'")
    if str(data.get("kind", "")).strip() != CHAPTER_WRITE_STATE_KIND:
        errors.append(
            f"chapter_write_state.kind must be {CHAPTER_WRITE_STATE_KIND!r}",
        )
    top = str(data.get("status", "")).strip()
    if top not in _STATUS_TOP:
        errors.append(
            f"chapter_write_state.status must be one of {sorted(_STATUS_TOP)}",
        )
    order = data.get("order")
    if not isinstance(order, list):
        errors.append("chapter_write_state.order must be an array")
        order = []
    by_id = data.get("by_id")
    if not isinstance(by_id, dict):
        errors.append("chapter_write_state.by_id must be an object")
        by_id = {}
    seen: set[str] = set()
    for index, cid in enumerate(order):
        cid_s = str(cid).strip() if cid is not None else ""
        if not cid_s:
            errors.append(f"chapter_write_state.order[{index}] must be non-empty")
            continue
        if cid_s in seen:
            errors.append(f"chapter_write_state.order duplicate: {cid_s!r}")
        seen.add(cid_s)
        if cid_s not in by_id:
            errors.append(f"chapter_write_state.by_id missing order entry {cid_s!r}")
    for cid, entry in by_id.items():
        cid_s = str(cid).strip()
        if cid_s not in seen:
            errors.append(f"chapter_write_state.by_id has orphan key {cid_s!r}")
        if not isinstance(entry, dict):
            errors.append(f"chapter_write_state.by_id[{cid_s!r}] must be an object")
            continue
        st = str(entry.get("status", "")).strip()
        if st not in _STATUS_UNIT:
            errors.append(
                f"chapter_write_state.by_id[{cid_s!r}].status must be one of "
                f"{sorted(_STATUS_UNIT)}",
            )
    return errors


def compute_top_status(order: list[str], by_id: dict[str, Any]) -> str:
    if not order:
        return "complete"
    statuses = [
        str((by_id.get(cid) or {}).get("status", "")).strip() for cid in order
    ]
    if statuses and all(s == "done" for s in statuses):
        return "complete"
    if all(s == "pending" for s in statuses):
        return "pending"
    return "in_progress"


def next_chapter_id(order: list[str], by_id: dict[str, Any]) -> str | None:
    for cid in order:
        st = str((by_id.get(cid) or {}).get("status", "")).strip()
        if st != "done":
            return cid
    return None


def is_complete(data: dict[str, Any]) -> bool:
    return str(data.get("status", "")).strip() == "complete"


def normalize_chapter_write_state(data: dict[str, Any]) -> dict[str, Any]:
    order = [str(x).strip() for x in (data.get("order") or []) if str(x).strip()]
    raw_by = data.get("by_id") if isinstance(data.get("by_id"), dict) else {}
    by_id: dict[str, Any] = {}
    for cid in order:
        entry = raw_by.get(cid) if isinstance(raw_by.get(cid), dict) else {}
        by_id[cid] = {
            "status": str(entry.get("status", "pending")).strip() or "pending",
            "leaf_id": str(entry.get("leaf_id", "")).strip(),
            "lens": str(entry.get("lens", "")).strip().upper(),
            "started_at": entry.get("started_at"),
            "completed_at": entry.get("completed_at"),
        }
    top = compute_top_status(order, by_id)
    current = data.get("current")
    current_s = str(current).strip() if current is not None else ""
    out: dict[str, Any] = {
        "version": "1",
        "kind": CHAPTER_WRITE_STATE_KIND,
        "status": top,
        "order": order,
        "current": current_s or None,
        "by_id": by_id,
    }
    if data.get("updated_at") is not None:
        out["updated_at"] = data.get("updated_at")
    return out


def load_chapter_write_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"chapter_write_state file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid chapter_write_state JSON: {exc}") from exc
    errors = validate_chapter_write_state(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_chapter_write_state(data)


def save_chapter_write_state(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_chapter_write_state(data if isinstance(data, dict) else {})
    errors = validate_chapter_write_state(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return normalized


def require_complete(revision_dir: Path) -> str | None:
    """Return error message if write-state missing or not complete; else None."""
    path = chapter_write_state_path(revision_dir)
    if not path.is_file():
        return f"chapter write-state missing: {path.name}"
    try:
        data = load_chapter_write_state(path)
    except ValueError as exc:
        return f"invalid chapter write-state: {exc}"
    if not is_complete(data):
        return (
            f"chapter write-state status is {data.get('status')!r} "
            "(required complete)"
        )
    return None
