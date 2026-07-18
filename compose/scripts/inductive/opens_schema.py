#!/usr/bin/env python3
"""Schema and I/O for revision ``inductive-opens.json`` (K4 Phase 1a).

Design rationale (source repo, why-only):
docs/domain/archive/compose/archive-2.0/compose-fact-first-k4-fact-native-design.md §4.1.

Doc-level flat open list — discovery ledger separate from per-lens maturity
and from fact membership. Wired by ``inductive_g3_section_control`` (K4 Phase 2).

Shape: JSON array of open objects (no envelope). Id form ``O-<n>`` contiguous
from O-1. Status is explicit (open|settled|deferred|rejected) — replaces the
legacy "which array am I in" encoding on section JSON.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

OPENS_BASENAME = "inductive-opens.json"

OPEN_STATUSES = frozenset({"open", "settled", "deferred", "rejected"})
# Opens carry discovered provenance only (seed bypasses open → facts directly).
TRIGGERS = frozenset({"human", "ai"})
MEANS = frozenset(
    {"probe", "direct", "view", "ai_scan", "intent_baseline"}
)
CONFIDENCES = frozenset({"direct", "inferred"})

_OPEN_REQUIRED = ("id", "status", "source", "kw", "blocking", "problem")
_OPEN_OPTIONAL = frozenset(
    {
        "detected_under",
        "leaning",
        "confidence",
        "intent_ref",
        "hangs_under",
        "resolved_by",
        "note",
        "reason",
        "code_refs",
    }
)
_OPEN_ID_RE = re.compile(r"^O-(\d+)$")
_FACT_ID_RE = re.compile(r"^F-\d+$")


def opens_path(out_dir: Path) -> Path:
    """Path to ``inductive-opens.json`` under the inductive out/revision dir."""
    return Path(out_dir) / OPENS_BASENAME


def mint_open_id(seq: int) -> str:
    return f"O-{seq}"


def next_open_seq(opens: list[dict[str, Any]]) -> int:
    """Return next contiguous O-n sequence number (1-based)."""
    max_n = 0
    for item in opens:
        if not isinstance(item, dict):
            continue
        m = _OPEN_ID_RE.match(str(item.get("id", "")))
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


def _validate_source_stamp(prefix: str, source: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(source, dict):
        errors.append(f"{prefix}.source must be an object {{trigger, means}}")
        return errors
    trigger = str(source.get("trigger", "")).strip().lower()
    means = str(source.get("means", "")).strip().lower()
    if trigger not in TRIGGERS:
        errors.append(f"{prefix}.source.trigger invalid: {trigger!r}")
    if means not in MEANS:
        errors.append(f"{prefix}.source.means invalid: {means!r}")
    extra = set(source) - {"trigger", "means"}
    if extra:
        errors.append(f"{prefix}.source unexpected fields {sorted(extra)}")
    return errors


def _validate_resolved_by(prefix: str, resolved_by: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(resolved_by, list):
        errors.append(f"{prefix}.resolved_by must be an array")
        return errors
    seen: set[str] = set()
    for i, item in enumerate(resolved_by):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{prefix}.resolved_by[{i}] must be a non-empty string")
            continue
        fid = item.strip()
        if not _FACT_ID_RE.match(fid):
            errors.append(f"{prefix}.resolved_by[{i}] must match F-<n>, got {fid!r}")
        if fid in seen:
            errors.append(f"{prefix}.resolved_by duplicate: {fid!r}")
        seen.add(fid)
    return errors


def _validate_open(entry: dict[str, Any], *, expected_n: int) -> list[str]:
    errors: list[str] = []
    oid_raw = entry.get("id")
    where = f"open {oid_raw!r}"

    for field in _OPEN_REQUIRED:
        if field not in entry:
            errors.append(f"{where}: missing required field {field!r}")

    if not isinstance(oid_raw, str) or not oid_raw.strip():
        errors.append(f"{where}: id must be a non-empty string")
        oid = ""
    else:
        oid = oid_raw.strip()
        m = _OPEN_ID_RE.match(oid)
        if not m:
            errors.append(f"{where}: id must match O-<n>, got {oid!r}")
        else:
            n = int(m.group(1))
            if n != expected_n:
                errors.append(
                    f"{where}: id must be O-{expected_n} "
                    f"(got {oid!r}; ids must be contiguous from O-1)"
                )

    status = str(entry.get("status", "")).strip().lower()
    if "status" in entry and status not in OPEN_STATUSES:
        errors.append(f"{where}: invalid status {status!r}")

    if "source" in entry:
        errors.extend(_validate_source_stamp(where, entry["source"]))

    if "kw" in entry and not isinstance(entry["kw"], (int, str)):
        errors.append(f"{where}: kw must be int or str")

    if "blocking" in entry and not isinstance(entry.get("blocking"), bool):
        errors.append(f"{where}: blocking must be a bool")

    problem = entry.get("problem")
    if "problem" in entry and (not isinstance(problem, str) or not problem.strip()):
        errors.append(f"{where}: problem must be a non-empty string")

    if "detected_under" in entry and entry["detected_under"] is not None:
        du = entry["detected_under"]
        if not isinstance(du, str) or not du.strip():
            errors.append(
                f"{where}: detected_under must be a non-empty string or null"
            )

    if "confidence" in entry and entry["confidence"] is not None:
        conf = str(entry["confidence"]).strip().lower()
        if conf not in CONFIDENCES:
            errors.append(f"{where}: invalid confidence {conf!r}")

    for opt_str in ("leaning", "intent_ref", "hangs_under", "note", "reason"):
        if opt_str in entry and entry[opt_str] is not None:
            if not isinstance(entry[opt_str], str):
                errors.append(f"{where}: {opt_str} must be a string when present")

    if "code_refs" in entry and entry["code_refs"] is not None:
        if not isinstance(entry["code_refs"], list):
            errors.append(f"{where}: code_refs must be a list")

    if "resolved_by" in entry and entry["resolved_by"] is not None:
        errors.extend(_validate_resolved_by(where, entry["resolved_by"]))

    # Status-conditional rules
    if status == "settled":
        rb = entry.get("resolved_by")
        if not isinstance(rb, list) or not rb:
            errors.append(
                f"{where}: status=settled requires non-empty resolved_by"
            )
    elif status in OPEN_STATUSES:
        rb = entry.get("resolved_by")
        if isinstance(rb, list) and rb:
            errors.append(
                f"{where}: resolved_by must be empty unless status=settled"
            )
    if status == "rejected":
        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{where}: status=rejected requires non-empty reason")
    if status == "deferred":
        note = entry.get("note")
        if not isinstance(note, str) or not note.strip():
            errors.append(f"{where}: status=deferred requires non-empty note")

    extra = set(entry) - set(_OPEN_REQUIRED) - _OPEN_OPTIONAL
    if extra:
        errors.append(f"{where}: unexpected fields {sorted(extra)}")

    return errors


def validate_opens(opens: Any) -> list[str]:
    """Return validation errors for an opens array (empty list = valid)."""
    if not isinstance(opens, list):
        return ["opens root must be a JSON array"]
    # Empty array is legal (no opens yet).
    errors: list[str] = []
    seen_ids: set[str] = set()
    expected_n = 1
    for index, entry in enumerate(opens):
        if not isinstance(entry, dict):
            errors.append(f"opens[{index}] must be an object")
            continue
        errors.extend(_validate_open(entry, expected_n=expected_n))
        oid = str(entry.get("id", "")).strip()
        if oid:
            if oid in seen_ids:
                errors.append(f"opens[{index}]: duplicate id {oid!r}")
            seen_ids.add(oid)
            m = _OPEN_ID_RE.match(oid)
            if m and int(m.group(1)) == expected_n:
                expected_n += 1
    return errors


def normalize_open(entry: dict[str, Any]) -> dict[str, Any]:
    source_raw = entry.get("source") or {}
    out: dict[str, Any] = {
        "id": str(entry["id"]).strip(),
        "status": str(entry["status"]).strip().lower(),
        "source": {
            "trigger": str(source_raw.get("trigger", "")).strip().lower(),
            "means": str(source_raw.get("means", "")).strip().lower(),
        },
        "kw": entry["kw"],
        "blocking": bool(entry["blocking"]),
        "problem": str(entry["problem"]).strip(),
    }
    if "detected_under" in entry:
        du = entry["detected_under"]
        out["detected_under"] = (
            None if du is None else str(du).strip().upper()
        )
    for opt in ("leaning", "intent_ref", "hangs_under", "note", "reason"):
        if opt in entry and entry[opt] is not None:
            out[opt] = str(entry[opt]).strip()
    if "confidence" in entry and entry["confidence"] is not None:
        out["confidence"] = str(entry["confidence"]).strip().lower()
    if "resolved_by" in entry and entry["resolved_by"] is not None:
        out["resolved_by"] = [str(x).strip() for x in entry["resolved_by"]]
    if "code_refs" in entry and entry["code_refs"] is not None:
        out["code_refs"] = [str(x).strip() for x in entry["code_refs"]]
    return out


def load_opens(path: Path) -> list[dict[str, Any]]:
    """Load and validate opens file; missing file → empty list."""
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid opens JSON: {exc}") from exc
    errors = validate_opens(data)
    if errors:
        raise ValueError("; ".join(errors))
    return [normalize_open(entry) for entry in data]


def save_opens(path: Path, opens: list[dict[str, Any]]) -> None:
    """Validate raw, normalize, and write opens array."""
    errors = validate_opens(opens)
    if errors:
        raise ValueError("; ".join(errors))
    normalized = [normalize_open(o) for o in opens]
    errors = validate_opens(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def blocking_open_items(opens: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Opens with status=open and blocking=True (Exit predicate feed)."""
    return [
        o
        for o in opens
        if o.get("status") == "open" and o.get("blocking") is True
    ]
