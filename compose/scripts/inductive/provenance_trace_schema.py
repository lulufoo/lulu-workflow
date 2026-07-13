#!/usr/bin/env python3
"""Schema and I/O for the three provenance trace files (Gate G5).

One trace file per upstream role (axis semantics: compose/references/
provenance-algorithm-semantics.md; design rationale, source repo, why-only:
docs/biz/compose-provenance-mechanism.md):

    provenance-trace-intent.json   role=intent-baseline  (意图基准 / axis 1+2)
    provenance-trace-scope.json    role=scope            (派生父级 / axis 1+2)
    provenance-trace-norm.json     role=norm-constraint  (规范约束 / axis 1 only)

Each delta row records ONE named deviation found by G5. G5 is a
find-and-name-only gate: rows are always written with
status='pending-signoff' and signoff=null; sign-off / delivery blocking is
a later phase.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROLES: tuple[str, ...] = ("intent-baseline", "scope", "norm-constraint")

ROLE_FILES: dict[str, str] = {
    "intent-baseline": "provenance-trace-intent.json",
    "scope": "provenance-trace-scope.json",
    "norm-constraint": "provenance-trace-norm.json",
}

# Valid (role, axis) -> allowed buckets. Axis 1 = overreach/conflict scan;
# axis 2 = coverage/fulfillment pass. norm-constraint has no axis 2.
VALID_BUCKETS: dict[tuple[str, int], frozenset[str]] = {
    ("intent-baseline", 1): frozenset({"扩充意图", "新增意图", "不一致"}),
    ("intent-baseline", 2): frozenset({"未履行意图"}),
    ("scope", 1): frozenset({"不一致"}),
    ("scope", 2): frozenset({"遗漏明确决策"}),
    ("norm-constraint", 1): frozenset({"违反"}),
}

STATUS_PENDING = "pending-signoff"

GATE_STATE_FILE = "provenance-gate-state.json"
GATE_STATUSES = frozenset({"active", "closed"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def trace_path(out_dir: Path, role: str) -> Path:
    if role not in ROLE_FILES:
        raise ValueError(f"unknown provenance role: {role!r}")
    return out_dir / ROLE_FILES[role]


def new_trace(*, role: str, cycle_id: str = "", stage: str = "") -> dict[str, Any]:
    if role not in ROLES:
        raise ValueError(f"unknown provenance role: {role!r}")
    return {
        "version": "1",
        "role": role,
        "cycle_id": cycle_id,
        "stage": stage,
        "deltas": [],
        "updated_at": _now_iso(),
    }


def normalize_delta(delta: dict[str, Any]) -> dict[str, Any]:
    """Return a delta row with all fields present and normalized."""
    axis_raw = delta.get("axis")
    try:
        axis = int(axis_raw)
    except (TypeError, ValueError):
        axis = 0
    code_refs = delta.get("code_refs") or []
    if not isinstance(code_refs, list):
        code_refs = [str(code_refs)]
    blocking = delta.get("blocking")
    return {
        "id": str(delta.get("id", "")).strip(),
        "axis": axis,
        "role": str(delta.get("role", "")).strip(),
        "bucket": str(delta.get("bucket", "")).strip(),
        "section": delta.get("section") if delta.get("section") not in ("", None) else None,
        "upstream_anchor": str(delta.get("upstream_anchor", "")).strip(),
        "description": str(delta.get("description", "")).strip(),
        "code_refs": [str(c) for c in code_refs],
        "blocking": True if blocking is None else bool(blocking),
        "status": STATUS_PENDING,
        "signoff": None,
    }


def validate_delta(delta: dict[str, Any], *, role: str) -> list[str]:
    """Return validation errors for a single delta row."""
    errors: list[str] = []
    norm = normalize_delta(delta)

    if not norm["id"]:
        errors.append("delta.id must be non-empty")

    if norm["role"] != role:
        errors.append(f"delta.role {norm['role']!r} does not match trace role {role!r}")

    axis = norm["axis"]
    if axis not in (1, 2):
        errors.append(f"delta.axis must be 1 or 2, got {axis!r}")
        return errors

    allowed = VALID_BUCKETS.get((role, axis))
    if allowed is None:
        errors.append(f"role {role!r} has no axis {axis}")
    elif norm["bucket"] not in allowed:
        errors.append(
            f"delta.bucket {norm['bucket']!r} invalid for {role} axis {axis} "
            f"(allowed: {sorted(allowed)})"
        )

    if axis == 1 and not norm["section"]:
        errors.append("axis 1 delta requires a section key")
    if axis == 2 and norm["section"] is not None:
        errors.append("axis 2 delta must have section=null")

    if not norm["upstream_anchor"]:
        errors.append("delta.upstream_anchor must be non-empty")
    if not norm["description"]:
        errors.append("delta.description must be non-empty")

    if norm["status"] != STATUS_PENDING:
        errors.append(f"delta.status must be {STATUS_PENDING!r}")

    return errors


def validate_trace(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r}")
    role = str(data.get("role", ""))
    if role not in ROLES:
        errors.append(f"invalid role: {role!r}")
        return errors
    deltas = data.get("deltas")
    if not isinstance(deltas, list):
        errors.append("deltas must be an array")
        return errors
    seen_ids: set[str] = set()
    for i, delta in enumerate(deltas):
        if not isinstance(delta, dict):
            errors.append(f"deltas[{i}] must be an object")
            continue
        for err in validate_delta(delta, role=role):
            errors.append(f"deltas[{i}]: {err}")
        did = str(delta.get("id", "")).strip()
        if did and did in seen_ids:
            errors.append(f"deltas[{i}]: duplicate id {did!r}")
        seen_ids.add(did)
    return errors


def load_trace(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"provenance trace not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_trace(data)
    if errors:
        raise ValueError("; ".join(errors))
    return data


def save_trace(path: Path, data: dict[str, Any]) -> None:
    normalized = dict(data)
    normalized["deltas"] = [normalize_delta(d) for d in data.get("deltas", [])]
    normalized["updated_at"] = _now_iso()
    errors = validate_trace(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(normalized, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def gate_state_path(out_dir: Path) -> Path:
    return out_dir / GATE_STATE_FILE


def new_gate_state(*, cycle_id: str = "", stage: str = "") -> dict[str, Any]:
    return {
        "version": "1",
        "cycle_id": cycle_id,
        "stage": stage,
        "gate": "G5",
        "status": "active",
        "closed_at": None,
        "updated_at": _now_iso(),
    }


def load_gate_state(out_dir: Path) -> dict[str, Any]:
    path = gate_state_path(out_dir)
    if not path.exists():
        raise FileNotFoundError(f"provenance gate state not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    status = str(data.get("status", ""))
    if status not in GATE_STATUSES:
        raise ValueError(f"invalid provenance gate status: {status!r}")
    return data


def save_gate_state(out_dir: Path, state: dict[str, Any]) -> None:
    status = str(state.get("status", ""))
    if status not in GATE_STATUSES:
        raise ValueError(f"invalid provenance gate status: {status!r}")
    payload = dict(state)
    payload["gate"] = "G5"
    payload["updated_at"] = _now_iso()
    path = gate_state_path(out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def append_delta(data: dict[str, Any], delta: dict[str, Any]) -> dict[str, Any]:
    """Return a new trace dict with the normalized delta appended."""
    role = str(data.get("role", ""))
    errors = validate_delta(delta, role=role)
    if errors:
        raise ValueError("; ".join(errors))
    norm = normalize_delta(delta)
    existing_ids = {str(d.get("id", "")) for d in data.get("deltas", [])}
    if norm["id"] in existing_ids:
        raise ValueError(f"duplicate delta id: {norm['id']!r}")
    updated = dict(data)
    updated["deltas"] = list(data.get("deltas", [])) + [norm]
    return updated
