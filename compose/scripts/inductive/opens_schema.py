#!/usr/bin/env python3
"""Schema and I/O for slice ``inductive-opens.json``.

JSON array of open objects (no envelope). IDs are ``O-n`` (n >= 1),
monotonic and never reused; gaps are allowed.

Design rationale:
docs/domain/archive/compose/archive-34.0/compose-g3-open-point-loop-refactor-design.md
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent.parent / "section"
if str(_SECTION) not in sys.path:
    sys.path.insert(0, str(_SECTION))

from compose_state_lock import durable_write_json  # noqa: E402

OPENS_BASENAME = "inductive-opens.json"
OPEN_STATUSES = frozenset({"open", "settled", "deferred", "rejected"})
ACTORS = frozenset({"human", "ai"})
MEANS = frozenset({"collision", "direct", "noticed", "detect", "audit"})

_OPEN_REQUIRED = ("id", "status", "source", "question", "basis", "blocking")
_OPEN_OPTIONAL = frozenset({"resolved_by", "note", "reason", "code_refs"})
_OPEN_ID_RE = re.compile(r"^O-([1-9]\d*)$")
_FACT_ID_RE = re.compile(r"^F-([1-9]\d*)$")


def opens_path(out_dir: Path) -> Path:
    """Path to ``inductive-opens.json`` under the working slice."""
    return Path(out_dir) / OPENS_BASENAME


def mint_open_id(seq: int) -> str:
    return f"O-{seq}"


def next_open_seq(opens: list[dict[str, Any]]) -> int:
    """Return next O-n sequence number (max existing n + 1)."""
    max_n = 0
    for item in opens:
        if not isinstance(item, dict):
            continue
        match = _OPEN_ID_RE.match(str(item.get("id", "")))
        if match:
            max_n = max(max_n, int(match.group(1)))
    return max_n + 1


def _validate_source_stamp(prefix: str, source: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(source, dict):
        errors.append(f"{prefix}.source must be an object {{actor, means}}")
        return errors
    actor = str(source.get("actor", "")).strip().lower()
    means = str(source.get("means", "")).strip().lower()
    if actor not in ACTORS:
        errors.append(f"{prefix}.source.actor invalid: {actor!r}")
    if means not in MEANS:
        errors.append(f"{prefix}.source.means invalid: {means!r}")
    extra = set(source) - {"actor", "means"}
    if extra:
        errors.append(f"{prefix}.source unexpected fields {sorted(extra)}")
    return errors


def _validate_resolved_by(prefix: str, resolved_by: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(resolved_by, list):
        errors.append(f"{prefix}.resolved_by must be an array")
        return errors
    seen: set[str] = set()
    for index, item in enumerate(resolved_by):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{prefix}.resolved_by[{index}] must be a non-empty string")
            continue
        fact_id = item.strip()
        if not _FACT_ID_RE.match(fact_id):
            errors.append(
                f"{prefix}.resolved_by[{index}] must match F-<n>, got {fact_id!r}"
            )
        if fact_id in seen:
            errors.append(f"{prefix}.resolved_by duplicate: {fact_id!r}")
        seen.add(fact_id)
    return errors


def _validate_code_refs(prefix: str, code_refs: Any) -> list[str]:
    if not isinstance(code_refs, list):
        return [f"{prefix}.code_refs must be a list"]
    errors: list[str] = []
    for index, item in enumerate(code_refs):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{prefix}.code_refs[{index}] must be a non-empty string")
    return errors


def _validate_open(entry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    oid_raw = entry.get("id")
    where = f"open {oid_raw!r}"

    for field in _OPEN_REQUIRED:
        if field not in entry:
            errors.append(f"{where}: missing required field {field!r}")

    if not isinstance(oid_raw, str) or not oid_raw.strip():
        errors.append(f"{where}: id must be a non-empty string")
    else:
        oid = oid_raw.strip()
        if not _OPEN_ID_RE.match(oid):
            errors.append(f"{where}: id must match O-<n> with n>=1, got {oid!r}")

    status = str(entry.get("status", "")).strip().lower()
    if "status" in entry and status not in OPEN_STATUSES:
        errors.append(f"{where}: invalid status {status!r}")

    if "source" in entry:
        errors.extend(_validate_source_stamp(where, entry["source"]))

    if "blocking" in entry and not isinstance(entry.get("blocking"), bool):
        errors.append(f"{where}: blocking must be a bool")

    for field in ("question", "basis"):
        if field in entry and (
            not isinstance(entry.get(field), str) or not str(entry.get(field)).strip()
        ):
            errors.append(f"{where}: {field} must be a non-empty string")

    if "resolved_by" in entry and entry["resolved_by"] is not None:
        errors.extend(_validate_resolved_by(where, entry["resolved_by"]))
    if "code_refs" in entry and entry["code_refs"] is not None:
        errors.extend(_validate_code_refs(where, entry["code_refs"]))
    for opt_str in ("note", "reason"):
        if opt_str in entry and entry[opt_str] is not None:
            if not isinstance(entry[opt_str], str) or not str(entry[opt_str]).strip():
                errors.append(f"{where}: {opt_str} must be a non-empty string")

    if status == "settled":
        resolved_by = entry.get("resolved_by")
        if not isinstance(resolved_by, list) or not resolved_by:
            errors.append(f"{where}: status=settled requires non-empty resolved_by")
    elif "resolved_by" in entry and entry.get("resolved_by"):
        errors.append(f"{where}: resolved_by is only valid when status=settled")

    if status == "deferred":
        note = entry.get("note")
        if not isinstance(note, str) or not note.strip():
            errors.append(f"{where}: status=deferred requires non-empty note")
    elif "note" in entry and entry.get("note"):
        errors.append(f"{where}: note is only valid when status=deferred")

    if status == "rejected":
        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{where}: status=rejected requires non-empty reason")
    elif "reason" in entry and entry.get("reason"):
        errors.append(f"{where}: reason is only valid when status=rejected")

    extra = set(entry) - set(_OPEN_REQUIRED) - _OPEN_OPTIONAL
    if extra:
        errors.append(f"{where}: unexpected fields {sorted(extra)}")
    return errors


def validate_opens(opens: Any) -> list[str]:
    """Return validation errors for an opens array (empty list = valid)."""
    if not isinstance(opens, list):
        return ["opens root must be a JSON array"]
    errors: list[str] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(opens):
        if not isinstance(entry, dict):
            errors.append(f"opens[{index}] must be an object")
            continue
        errors.extend(_validate_open(entry))
        oid = str(entry.get("id", "")).strip()
        if oid:
            if oid in seen_ids:
                errors.append(f"opens[{index}]: duplicate id {oid!r}")
            seen_ids.add(oid)
    return errors


def normalize_open(entry: dict[str, Any]) -> dict[str, Any]:
    source_raw = entry.get("source") or {}
    out: dict[str, Any] = {
        "id": str(entry["id"]).strip(),
        "status": str(entry["status"]).strip().lower(),
        "source": {
            "actor": str(source_raw.get("actor", "")).strip().lower(),
            "means": str(source_raw.get("means", "")).strip().lower(),
        },
        "question": str(entry["question"]).strip(),
        "basis": str(entry["basis"]).strip(),
        "blocking": bool(entry["blocking"]),
    }
    if "resolved_by" in entry and entry["resolved_by"] is not None:
        out["resolved_by"] = [str(item).strip() for item in entry["resolved_by"]]
    if "note" in entry and entry["note"] is not None:
        out["note"] = str(entry["note"]).strip()
    if "reason" in entry and entry["reason"] is not None:
        out["reason"] = str(entry["reason"]).strip()
    if "code_refs" in entry and entry["code_refs"] is not None:
        out["code_refs"] = [str(item).strip() for item in entry["code_refs"]]
    return out


def load_opens(path: Path) -> list[dict[str, Any]]:
    """Load and validate opens file; missing file → empty list."""
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid opens JSON: {exc}") from exc
    if not isinstance(data, list):
        raise ValueError("opens root must be a JSON array")
    errors = validate_opens(data)
    if errors:
        raise ValueError("; ".join(errors))
    return [normalize_open(entry) for entry in data]


def save_opens(path: Path, opens: list[dict[str, Any]]) -> None:
    """Validate, normalize, and write the opens array."""
    errors = validate_opens(opens)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = [normalize_open(item) for item in opens]
    errors = validate_opens(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    durable_write_json(path, normalized)


def blocking_open_items(opens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Opens with status=open and blocking=True."""
    return [
        item
        for item in opens
        if item.get("status") == "open" and item.get("blocking") is True
    ]
