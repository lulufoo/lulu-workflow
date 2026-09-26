#!/usr/bin/env python3
"""Schema I/O for ``deductive-pending.json`` (confirm-gate SoT).

Design rationale (source repo, why-only):
docs/archive/lulu-workflow/compose/archive-3.0/compose-deductive-runner-architecture-design.md §4.5.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

PENDING_BASENAME = "deductive-pending.json"
PENDING_KINDS = frozenset(
    {
        "edge_hole",
        "off_edge",
        "undecided",
        "quarantine_unref",
        "true_gap",
        "kw_shortfall",  # ceiling×KW: published KW table not met; human accept or seed
    }
)
PENDING_STATUSES = frozenset({"open", "resolved", "escalated", "out_of_scope"})
_ITEM_ID_RE = re.compile(r"^P-(\d+)$")


def pending_path(revision_dir: Path) -> Path:
    return Path(revision_dir) / PENDING_BASENAME


def empty_pending() -> dict[str, Any]:
    return {"version": 1, "items": []}


def load_pending(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_pending()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("deductive-pending.json must be an object")
    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("deductive-pending.items must be an array")
    return {"version": int(data.get("version") or 1), "items": items}


def save_pending(path: Path, data: dict[str, Any]) -> None:
    errors = validate_pending(data)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_pending(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["pending root must be an object"]
    items = data.get("items")
    if not isinstance(items, list):
        return ["pending.items must be an array"]
    seen: set[str] = set()
    for i, item in enumerate(items):
        prefix = f"items[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        pid = item.get("id")
        if not isinstance(pid, str) or not _ITEM_ID_RE.match(pid.strip()):
            errors.append(f"{prefix}.id must match P-n")
        else:
            pid = pid.strip()
            if pid in seen:
                errors.append(f"duplicate pending id {pid}")
            seen.add(pid)
        kind = str(item.get("kind", "")).strip().lower()
        if kind not in PENDING_KINDS:
            errors.append(f"{prefix}.kind must be one of {sorted(PENDING_KINDS)}")
        status = str(item.get("status", "")).strip().lower()
        if status not in PENDING_STATUSES:
            errors.append(
                f"{prefix}.status must be one of {sorted(PENDING_STATUSES)}"
            )
        if not isinstance(item.get("summary"), str) or not item["summary"].strip():
            errors.append(f"{prefix}.summary must be a non-empty string")
    return errors


def next_pending_id(items: list[dict[str, Any]]) -> str:
    max_n = 0
    for item in items:
        m = _ITEM_ID_RE.match(str(item.get("id", "")).strip())
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"P-{max_n + 1}"


def open_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        i
        for i in data.get("items") or []
        if str(i.get("status", "")).strip().lower() == "open"
    ]
