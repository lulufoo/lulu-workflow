#!/usr/bin/env python3
"""Cycle delivered-refs.json and workflow-state delivered_refs helpers."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[2]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from workflow_common import CACHE_DIR  # noqa: E402

_FILE_NAME = "delivered-refs.json"
_VERSION = 1


@dataclass(frozen=True)
class DeliveredRef:
    """Upstream delivered document reference."""

    type: str
    path: str

    def to_dict(self) -> dict[str, str]:
        return {"type": self.type, "path": self.path}


def delivered_refs_file_path(cycle_id: str, project_root: Path) -> Path:
    return (project_root / CACHE_DIR / cycle_id / _FILE_NAME).resolve()


def _empty_file_payload() -> dict[str, Any]:
    return {"version": _VERSION, "entries": {}}


def load_delivered_refs_file(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Load {cycle_id}/delivered-refs.json; missing file returns empty entries."""
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
) -> None:
    """Upsert one delivered type in {cycle_id}/delivered-refs.json."""
    dtype = delivered_type.strip()
    if not dtype:
        raise ValueError("delivered_type must be non-empty")
    data = load_delivered_refs_file(cycle_id, project_root)
    entries = dict(data.get("entries") or {})
    entries[dtype] = {
        "delivered_type": dtype,
        "path": str(Path(path).resolve()),
        "revision": revision,
        "profile_id": profile_id,
        "delivered_at": datetime.now(timezone.utc).isoformat(),
        "source_workflow_state": source_workflow_state,
    }
    data["entries"] = entries
    save_delivered_refs_file(cycle_id, project_root, data)


def entry_path_ok(data: dict[str, Any], delivered_type: str) -> bool:
    entry = (data.get("entries") or {}).get(delivered_type)
    if not isinstance(entry, dict):
        return False
    raw = str(entry.get("path", "")).strip()
    return bool(raw) and Path(raw).is_file()


def ref_from_file_entry(delivered_type: str, data: dict[str, Any]) -> DeliveredRef | None:
    entry = (data.get("entries") or {}).get(delivered_type)
    if not isinstance(entry, dict):
        return None
    raw_path = str(entry.get("path", "")).strip()
    if not raw_path:
        return None
    return DeliveredRef(type=delivered_type, path=raw_path)


def serialize_delivered_refs(refs: list[DeliveredRef]) -> str:
    return json.dumps([r.to_dict() for r in refs], ensure_ascii=False)


def parse_delivered_refs(state: dict[str, Any]) -> list[DeliveredRef]:
    raw = state.get("delivered_refs", "[]")
    if isinstance(raw, list):
        items = raw
    else:
        text = str(raw).strip() or "[]"
        items = json.loads(text)
    if not isinstance(items, list):
        raise ValueError("delivered_refs must be a JSON array")
    refs: list[DeliveredRef] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("delivered_refs items must be objects")
        dtype = str(item.get("type", "")).strip()
        path = str(item.get("path", "")).strip()
        if not dtype or not path:
            raise ValueError("delivered_refs item requires non-empty type and path")
        refs.append(DeliveredRef(type=dtype, path=path))
    return refs


def delivered_path(state: dict[str, Any], delivered_type: str) -> str:
    for ref in parse_delivered_refs(state):
        if ref.type == delivered_type:
            return ref.path
    return ""


def product_ref_from_state(state: dict[str, Any]) -> str:
    return delivered_path(state, "product-spec")


def parse_scope_refs(state: dict[str, Any]) -> list[DeliveredRef]:
    """Parse scope_refs JSON array from workflow-state frontmatter."""
    raw = state.get("scope_refs", "[]")
    if isinstance(raw, list):
        items = raw
    else:
        text = str(raw).strip() or "[]"
        items = json.loads(text)
    if not isinstance(items, list):
        raise ValueError("scope_refs must be a JSON array")
    refs: list[DeliveredRef] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("scope_refs items must be objects")
        dtype = str(item.get("type", "")).strip()
        path = str(item.get("path", "")).strip()
        if not dtype or not path:
            raise ValueError("scope_refs item requires non-empty type and path")
        refs.append(DeliveredRef(type=dtype, path=path))
    return refs


def primary_scope_ref_from_state(state: dict[str, Any]) -> DeliveredRef | None:
    """Return scope_refs[0] from workflow-state snapshot."""
    refs = parse_scope_refs(state)
    if not refs:
        return None
    return refs[0]


def scope_doc_path_from_state(state: dict[str, Any]) -> str:
    ref = primary_scope_ref_from_state(state)
    return ref.path if ref is not None else ""
