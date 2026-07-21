#!/usr/bin/env python3
"""Schema and I/O for revision ``agenda.json`` (stage agenda).

Design rationale (source repo, why-only):
docs/domain/archive/workflow/stage-agenda-design.md
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

AGENDA_BASENAME = "agenda.json"
AGENDA_CLASSES = frozenset({"blocker", "note"})
AGENDA_STATUSES = frozenset({"open", "released", "waived"})
_ITEM_ID_RE = re.compile(r"^A-(\d+)$")


def agenda_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / AGENDA_BASENAME


def empty_agenda() -> dict[str, Any]:
    return {"version": 1, "items": []}


def mint_item_id(seq: int) -> str:
    return f"A-{seq}"


def next_item_seq(items: list[dict[str, Any]]) -> int:
    max_n = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        m = _ITEM_ID_RE.match(str(item.get("id", "")))
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


def load_agenda(path: Path) -> dict[str, Any]:
    """Load agenda; missing file → empty (deliver treats as no blockers)."""
    if not path.is_file():
        return empty_agenda()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("agenda.json must be an object")
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("agenda.items must be an array")
    return {"version": int(data.get("version") or 1), "items": items}


def save_agenda(path: Path, data: dict[str, Any]) -> None:
    errors = validate_agenda(data)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_agenda(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["agenda root must be an object"]
    items = data.get("items")
    if not isinstance(items, list):
        return ["agenda.items must be an array"]
    seen: set[str] = set()
    for i, item in enumerate(items):
        prefix = f"items[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        errors.extend(_validate_item(prefix, item, seen))
    return errors


def _validate_item(prefix: str, item: dict[str, Any], seen: set[str]) -> list[str]:
    errors: list[str] = []
    raw_id = item.get("id")
    if not isinstance(raw_id, str) or not _ITEM_ID_RE.match(raw_id.strip()):
        errors.append(f"{prefix}.id must match A-n")
    else:
        iid = raw_id.strip()
        if iid in seen:
            errors.append(f"duplicate agenda id {iid}")
        seen.add(iid)

    klass = str(item.get("class", "")).strip().lower()
    if klass not in AGENDA_CLASSES:
        errors.append(f"{prefix}.class must be one of {sorted(AGENDA_CLASSES)}")

    status = str(item.get("status", "")).strip().lower()
    if status not in AGENDA_STATUSES:
        errors.append(f"{prefix}.status must be one of {sorted(AGENDA_STATUSES)}")

    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        errors.append(f"{prefix}.text must be a non-empty string")

    if "async" in item and not isinstance(item.get("async"), bool):
        errors.append(f"{prefix}.async must be a bool when present")

    is_async = bool(item.get("async", False))
    if klass == "note" and is_async:
        errors.append(f"{prefix}: note must not set async=true")

    if status == "waived":
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{prefix}.reason is required when status=waived")
    return errors


def normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Return a canonical item dict for persistence."""
    klass = str(item["class"]).strip().lower()
    status = str(item["status"]).strip().lower()
    out: dict[str, Any] = {
        "id": str(item["id"]).strip(),
        "class": klass,
        "status": status,
        "text": str(item["text"]).strip(),
    }
    if klass == "blocker":
        out["async"] = bool(item.get("async", False))
    if status == "waived":
        out["reason"] = str(item.get("reason", "")).strip()
    elif isinstance(item.get("reason"), str) and item["reason"].strip():
        out["reason"] = item["reason"].strip()
    return out


def blocking_items(data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Items that must be empty for deliver: blocker ∧ open ∧ ¬async."""
    if not data or not isinstance(data.get("items"), list):
        return []
    out: list[dict[str, Any]] = []
    for item in data["items"]:
        if not isinstance(item, dict):
            continue
        if str(item.get("class", "")).strip().lower() != "blocker":
            continue
        if str(item.get("status", "")).strip().lower() != "open":
            continue
        if bool(item.get("async", False)):
            continue
        out.append(item)
    return out


def find_item(data: dict[str, Any], item_id: str) -> dict[str, Any] | None:
    want = item_id.strip()
    for item in data.get("items") or []:
        if isinstance(item, dict) and str(item.get("id", "")).strip() == want:
            return item
    return None
