#!/usr/bin/env python3
"""Schema and I/O for slice ``open-point-detect-receipts.json``.

Receipts are immutable once written; this module only validates shape.

Design rationale:
docs/domain/archive/compose/archive-42.0/compose-g3-coarsest-gap-ruler-design.md
docs/domain/archive/compose/compose-g3-detect-context-slim-design.md
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parents[2] / "section"
if str(_SECTION) not in sys.path:
    sys.path.insert(0, str(_SECTION))

from compose_state_lock import durable_write_json  # noqa: E402

RECEIPTS_BASENAME = "open-point-detect-receipts.json"
RECEIPTS_VERSION = 1
_ENVELOPE_KEYS = frozenset({"version", "receipts"})
_RECEIPT_KEYS = frozenset(
    {
        "id",
        "checked_lenses",
        "raw_candidate_count",
        "raw_candidate_digest",
        "final_open_ids",
        "zero_result",
        "lens_measurements",
    }
)
_RECEIPT_ID_RE = re.compile(r"^R-([1-9]\d*)$")
_OPEN_ID_RE = re.compile(r"^O-([1-9]\d*)$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


def open_point_receipts_path(slice_dir: Path) -> Path:
    return Path(slice_dir) / RECEIPTS_BASENAME


def empty_open_point_receipts() -> dict[str, Any]:
    return {"version": RECEIPTS_VERSION, "receipts": []}


def mint_receipt_id(seq: int) -> str:
    return f"R-{seq}"


def next_receipt_seq(receipts: list[dict[str, Any]]) -> int:
    max_n = 0
    for item in receipts:
        if not isinstance(item, dict):
            continue
        match = _RECEIPT_ID_RE.match(str(item.get("id", "")))
        if match:
            max_n = max(max_n, int(match.group(1)))
    return max_n + 1


def _validate_digest(prefix: str, field: str, value: Any) -> list[str]:
    if not isinstance(value, str) or not _HEX64_RE.match(value):
        return [f"{prefix}.{field} must be a lowercase SHA-256 hex digest"]
    return []


def _kw_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 4


def validate_lens_measurements(
    raw: Any,
    *,
    prefix: str,
    checked_lenses: list[str] | None = None,
    raw_candidate_count: int | None = None,
) -> list[str]:
    if not isinstance(raw, list) or not raw:
        return [f"{prefix} must be a non-empty array"]
    errors: list[str] = []
    seen: set[str] = set()
    gaps: list[Any] = []
    for index, item in enumerate(raw):
        where = f"{prefix}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object")
            continue
        extra = set(item) - {"lens", "start_kw", "gap_kw"}
        if extra:
            errors.append(f"{where} unexpected fields {sorted(extra)}")
        lens = str(item.get("lens", "")).strip().upper()
        if not lens:
            errors.append(f"{where}.lens must be a non-empty string")
        elif lens in seen:
            errors.append(f"{where}.lens duplicate: {lens!r}")
        else:
            seen.add(lens)
        if not _kw_int(item.get("start_kw")):
            errors.append(f"{where}.start_kw must be an int 0..4")
        gap = item.get("gap_kw")
        if gap is not None and not _kw_int(gap):
            errors.append(f"{where}.gap_kw must be null or an int 0..4")
        elif (
            gap is not None
            and _kw_int(item.get("start_kw"))
            and int(gap) < int(item["start_kw"])
        ):
            errors.append(f"{where}.gap_kw must be >= start_kw")
        gaps.append(gap)
    if checked_lenses is not None:
        required = {str(item).strip().upper() for item in checked_lenses if str(item).strip()}
        missing = sorted(required - seen)
        if missing:
            errors.append(f"{prefix} missing checked lenses {missing}")
    if raw_candidate_count is not None:
        all_null = bool(gaps) and all(item is None for item in gaps)
        if raw_candidate_count == 0 and not all_null:
            errors.append(f"{prefix} must have null gap_kw when raw_candidate_count is 0")
        if raw_candidate_count > 0 and all_null:
            errors.append(f"{prefix} must include a gap_kw when raw_candidate_count > 0")
    return errors


def normalize_lens_measurements(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        gap = item.get("gap_kw")
        out.append(
            {
                "lens": str(item.get("lens", "")).strip().upper(),
                "start_kw": int(item.get("start_kw") or 0),
                "gap_kw": None if gap is None else int(gap),
            }
        )
    return out


def parse_lens_measurements(
    raw: Any,
    *,
    checked_lenses: list[str] | None = None,
    raw_candidate_count: int | None = None,
) -> list[dict[str, Any]]:
    errors = validate_lens_measurements(
        raw,
        prefix="lens_measurements",
        checked_lenses=checked_lenses,
        raw_candidate_count=raw_candidate_count,
    )
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_lens_measurements(raw)


def _validate_receipt(entry: Any, index: int) -> list[str]:
    prefix = f"receipts[{index}]"
    if not isinstance(entry, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    extra = set(entry) - _RECEIPT_KEYS
    if extra:
        errors.append(f"{prefix} unexpected fields {sorted(extra)}")
    for field in _RECEIPT_KEYS:
        if field not in entry:
            errors.append(f"{prefix} missing required field {field!r}")
    receipt_id = str(entry.get("id", "")).strip()
    if not _RECEIPT_ID_RE.match(receipt_id):
        errors.append(f"{prefix}.id must match R-<n> with n>=1")
    lenses = entry.get("checked_lenses")
    if not isinstance(lenses, list) or not lenses:
        errors.append(f"{prefix}.checked_lenses must be a non-empty string list")
    elif any(not isinstance(item, str) or not item.strip() for item in lenses):
        errors.append(f"{prefix}.checked_lenses entries must be non-empty strings")
    errors.extend(_validate_digest(prefix, "raw_candidate_digest", entry.get("raw_candidate_digest")))
    count = entry.get("raw_candidate_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        errors.append(f"{prefix}.raw_candidate_count must be an int >= 0")
        count = None
    if not isinstance(entry.get("zero_result"), bool):
        errors.append(f"{prefix}.zero_result must be a bool")
    elif count is not None and entry["zero_result"] is not (count == 0):
        errors.append(f"{prefix}.zero_result must be true only when raw_candidate_count is 0")
    final_ids = entry.get("final_open_ids")
    if not isinstance(final_ids, list):
        errors.append(f"{prefix}.final_open_ids must be an array")
    else:
        seen: set[str] = set()
        for oid_index, oid in enumerate(final_ids):
            if not isinstance(oid, str) or not _OPEN_ID_RE.match(oid.strip()):
                errors.append(f"{prefix}.final_open_ids[{oid_index}] must match O-<n>")
                continue
            cleaned = oid.strip()
            if cleaned in seen:
                errors.append(f"{prefix}.final_open_ids duplicate: {cleaned!r}")
            seen.add(cleaned)
    checked = None
    if isinstance(lenses, list) and lenses:
        checked = [str(item).strip() for item in lenses if isinstance(item, str)]
    errors.extend(
        validate_lens_measurements(
            entry.get("lens_measurements"),
            prefix=f"{prefix}.lens_measurements",
            checked_lenses=checked,
            raw_candidate_count=count,
        )
    )
    return errors


def validate_open_point_receipts(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return ["open-point-detect-receipts root must be an object"]
    errors: list[str] = []
    extra = set(data) - _ENVELOPE_KEYS
    if extra:
        errors.append(f"open-point-detect-receipts unexpected fields {sorted(extra)}")
    if data.get("version") != RECEIPTS_VERSION:
        errors.append("open-point-detect-receipts.version must be 1")
    receipts = data.get("receipts")
    if not isinstance(receipts, list):
        errors.append("open-point-detect-receipts.receipts must be an array")
        return errors
    seen_ids: set[str] = set()
    for index, entry in enumerate(receipts):
        errors.extend(_validate_receipt(entry, index))
        if isinstance(entry, dict):
            receipt_id = str(entry.get("id", "")).strip()
            if receipt_id:
                if receipt_id in seen_ids:
                    errors.append(f"receipts[{index}]: duplicate id {receipt_id!r}")
                seen_ids.add(receipt_id)
    return errors


def normalize_receipt(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(entry["id"]).strip(),
        "checked_lenses": [str(item).strip() for item in entry.get("checked_lenses") or []],
        "raw_candidate_count": int(entry["raw_candidate_count"]),
        "raw_candidate_digest": str(entry["raw_candidate_digest"]).strip(),
        "final_open_ids": [str(item).strip() for item in entry.get("final_open_ids") or []],
        "zero_result": bool(entry["zero_result"]),
        "lens_measurements": normalize_lens_measurements(entry.get("lens_measurements")),
    }


def normalize_open_point_receipts(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": RECEIPTS_VERSION,
        "receipts": [
            normalize_receipt(entry)
            for entry in data.get("receipts") or []
            if isinstance(entry, dict)
        ],
    }


def load_open_point_receipts(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return empty_open_point_receipts()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid open-point-detect-receipts JSON: {exc}") from exc
    errors = validate_open_point_receipts(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_open_point_receipts(data)


def save_open_point_receipts(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    errors = validate_open_point_receipts(data)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = normalize_open_point_receipts(data)
    errors = validate_open_point_receipts(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    durable_write_json(path, normalized)
    return normalized
