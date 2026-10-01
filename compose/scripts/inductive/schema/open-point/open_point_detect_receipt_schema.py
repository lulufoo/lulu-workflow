#!/usr/bin/env python3
"""Schema and I/O for slice ``open-point-detect-receipts.json``.

Receipts are immutable once written; this module only validates shape.
Receipts are slim: ``id``, ``raw_candidate_count``, and per-lens
``lens_measurements`` (``lens`` + ``gap_kw``). Legacy fields from older
receipts are accepted on load and dropped by normalization.

Detect input arrives as per-lens verdicts (``lens``, ``gap_kw``,
``candidates``); ``parse_detect_verdicts`` enforces registry coverage and
the per-lens invariant ``gap_kw is null iff candidates is empty``.
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

RECEIPTS_BASENAME = "open-point-detect-receipts.json"
RECEIPTS_VERSION = 1
_ENVELOPE_KEYS = frozenset({"version", "receipts"})
_RECEIPT_KEYS = frozenset({"id", "raw_candidate_count", "lens_measurements"})
_LEGACY_RECEIPT_KEYS = frozenset(
    {"checked_lenses", "raw_candidate_digest", "final_open_ids", "zero_result"}
)
_VERDICT_KEYS = frozenset({"lens", "gap_kw", "candidates"})
_RECEIPT_ID_RE = re.compile(r"^R-([1-9]\d*)$")


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


def _kw_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 4


def validate_lens_measurements(raw: Any, *, prefix: str) -> list[str]:
    if not isinstance(raw, list) or not raw:
        return [f"{prefix} must be a non-empty array"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        where = f"{prefix}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object")
            continue
        extra = set(item) - {"lens", "gap_kw", "start_kw"}
        if extra:
            errors.append(f"{where} unexpected fields {sorted(extra)}")
        lens = str(item.get("lens", "")).strip().upper()
        if not lens:
            errors.append(f"{where}.lens must be a non-empty string")
        elif lens in seen:
            errors.append(f"{where}.lens duplicate: {lens!r}")
        else:
            seen.add(lens)
        gap = item.get("gap_kw")
        if gap is not None and not _kw_int(gap):
            errors.append(f"{where}.gap_kw must be null or an int 0..4")
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
                "gap_kw": None if gap is None else int(gap),
            }
        )
    return out


def validate_detect_verdicts(raw: Any, *, registry_lenses: list[str]) -> list[str]:
    if not isinstance(raw, list) or not raw:
        return ["verdicts must be a non-empty array"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        where = f"verdicts[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object")
            continue
        extra = set(item) - _VERDICT_KEYS
        if extra:
            errors.append(f"{where} unexpected fields {sorted(extra)}")
        lens = str(item.get("lens", "")).strip().upper()
        if not lens:
            errors.append(f"{where}.lens must be a non-empty string")
        elif lens in seen:
            errors.append(f"{where}.lens duplicate: {lens!r}")
        else:
            seen.add(lens)
        gap = item.get("gap_kw")
        if gap is not None and not _kw_int(gap):
            errors.append(f"{where}.gap_kw must be null or an int 0..4")
        candidates = item.get("candidates")
        if not isinstance(candidates, list) or any(
            not isinstance(entry, dict) for entry in candidates
        ):
            errors.append(f"{where}.candidates must be an array of objects")
        elif (gap is None) != (len(candidates) == 0):
            errors.append(
                f"{where} gap_kw must be null exactly when candidates is empty"
            )
    required = {str(item).strip().upper() for item in registry_lenses if str(item).strip()}
    missing = sorted(required - seen)
    if missing:
        errors.append(f"verdicts missing lenses {missing}")
    unknown = sorted(seen - required)
    if unknown:
        errors.append(f"verdicts unknown lenses {unknown}")
    return errors


def parse_detect_verdicts(
    raw: Any, *, registry_lenses: list[str]
) -> list[dict[str, Any]]:
    errors = validate_detect_verdicts(raw, registry_lenses=registry_lenses)
    if errors:
        raise ValueError("; ".join(errors))
    out: list[dict[str, Any]] = []
    for item in raw:
        gap = item.get("gap_kw")
        out.append(
            {
                "lens": str(item["lens"]).strip().upper(),
                "gap_kw": None if gap is None else int(gap),
                "candidates": [dict(entry) for entry in item.get("candidates") or []],
            }
        )
    return out


def _validate_receipt(entry: Any, index: int) -> list[str]:
    prefix = f"receipts[{index}]"
    if not isinstance(entry, dict):
        return [f"{prefix} must be an object"]
    errors: list[str] = []
    extra = set(entry) - _RECEIPT_KEYS - _LEGACY_RECEIPT_KEYS
    if extra:
        errors.append(f"{prefix} unexpected fields {sorted(extra)}")
    for field in _RECEIPT_KEYS:
        if field not in entry:
            errors.append(f"{prefix} missing required field {field!r}")
    receipt_id = str(entry.get("id", "")).strip()
    if not _RECEIPT_ID_RE.match(receipt_id):
        errors.append(f"{prefix}.id must match R-<n> with n>=1")
    count = entry.get("raw_candidate_count")
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        errors.append(f"{prefix}.raw_candidate_count must be an int >= 0")
    errors.extend(
        validate_lens_measurements(
            entry.get("lens_measurements"),
            prefix=f"{prefix}.lens_measurements",
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
        "raw_candidate_count": int(entry["raw_candidate_count"]),
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
