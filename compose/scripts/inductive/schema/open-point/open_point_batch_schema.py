#!/usr/bin/env python3
"""Schema and I/O for slice ``open-point-batches.json``.
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

BATCHES_BASENAME = "open-point-batches.json"
BATCHES_VERSION = 1
BATCH_STATUSES = frozenset({"active", "completed", "abandoned"})
_ENVELOPE_KEYS = frozenset({"version", "batches"})
_BATCH_KEYS = frozenset({"id", "status", "detect_receipt_id", "open_ids"})
_BATCH_ID_RE = re.compile(r"^B-([1-9]\d*)$")
_OPEN_ID_RE = re.compile(r"^O-([1-9]\d*)$")
_RECEIPT_ID_RE = re.compile(r"^R-([1-9]\d*)$")


def open_point_batches_path(slice_dir: Path) -> Path:
    return Path(slice_dir) / BATCHES_BASENAME


def empty_open_point_batches() -> dict[str, Any]:
    return {"version": BATCHES_VERSION, "batches": []}


def mint_batch_id(seq: int) -> str:
    return f"B-{seq}"


def next_batch_seq(batches: list[dict[str, Any]]) -> int:
    max_n = 0
    for item in batches:
        if not isinstance(item, dict):
            continue
        match = _BATCH_ID_RE.match(str(item.get("id", "")))
        if match:
            max_n = max(max_n, int(match.group(1)))
    return max_n + 1


def _validate_batch(entry: Any, index: int) -> list[str]:
    prefix = f"batches[{index}]"
    if not isinstance(entry, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    extra = set(entry) - _BATCH_KEYS
    if extra:
        errors.append(f"{prefix} unexpected fields {sorted(extra)}")
    for field in _BATCH_KEYS:
        if field not in entry:
            errors.append(f"{prefix} missing required field {field!r}")
    batch_id = str(entry.get("id", "")).strip()
    if not _BATCH_ID_RE.match(batch_id):
        errors.append(f"{prefix}.id must match B-<n> with n>=1")
    status = entry.get("status")
    if status not in BATCH_STATUSES:
        errors.append(f"{prefix}.status invalid: {status!r}")
    receipt_id = entry.get("detect_receipt_id")
    if receipt_id is not None:
        if not isinstance(receipt_id, str) or not _RECEIPT_ID_RE.match(receipt_id.strip()):
            errors.append(f"{prefix}.detect_receipt_id must be null or R-<n>")
    open_ids = entry.get("open_ids")
    if not isinstance(open_ids, list):
        errors.append(f"{prefix}.open_ids must be an array")
        return errors
    seen: set[str] = set()
    for oid_index, oid in enumerate(open_ids):
        if not isinstance(oid, str) or not _OPEN_ID_RE.match(oid.strip()):
            errors.append(f"{prefix}.open_ids[{oid_index}] must match O-<n>")
            continue
        cleaned = oid.strip()
        if cleaned in seen:
            errors.append(f"{prefix}.open_ids duplicate: {cleaned!r}")
        seen.add(cleaned)
    return errors


def validate_open_point_batches(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["open-point-batches root must be an object"]
    errors: list[str] = []
    extra = set(data) - _ENVELOPE_KEYS
    if extra:
        errors.append(f"open-point-batches unexpected fields {sorted(extra)}")
    if data.get("version") != BATCHES_VERSION:
        errors.append("open-point-batches.version must be 1")
    batches = data.get("batches")
    if not isinstance(batches, list):
        errors.append("open-point-batches.batches must be an array")
        return errors
    seen_ids: set[str] = set()
    active_count = 0
    for index, entry in enumerate(batches):
        errors.extend(_validate_batch(entry, index))
        if isinstance(entry, dict):
            batch_id = str(entry.get("id", "")).strip()
            if batch_id:
                if batch_id in seen_ids:
                    errors.append(f"batches[{index}]: duplicate id {batch_id!r}")
                seen_ids.add(batch_id)
            if entry.get("status") == "active":
                active_count += 1
    if active_count > 1:
        errors.append("at most one active batch is allowed")
    return errors


def normalize_batch(entry: dict[str, Any]) -> dict[str, Any]:
    receipt_id = entry.get("detect_receipt_id")
    return {
        "id": str(entry["id"]).strip(),
        "status": str(entry["status"]).strip().lower(),
        "detect_receipt_id": None if receipt_id is None else str(receipt_id).strip(),
        "open_ids": [str(item).strip() for item in entry.get("open_ids") or []],
    }


def normalize_open_point_batches(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": BATCHES_VERSION,
        "batches": [
            normalize_batch(entry)
            for entry in data.get("batches") or []
            if isinstance(entry, dict)
        ],
    }


def load_open_point_batches(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_open_point_batches()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid open-point-batches JSON: {exc}") from exc
    errors = validate_open_point_batches(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_open_point_batches(data)


def save_open_point_batches(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    errors = validate_open_point_batches(data)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = normalize_open_point_batches(data)
    errors = validate_open_point_batches(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    durable_write_json(path, normalized)
    return normalized
