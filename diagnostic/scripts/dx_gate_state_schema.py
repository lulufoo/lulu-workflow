#!/usr/bin/env python3
"""Schema and I/O for diagnostic gate-state.json."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dx_io import atomic_write_text

GATE_ORDER: tuple[str, ...] = (
    "O",
    "Q",
    "E",
    "D",
    "X",
    "R",
    "V",
    "RR",
    "DC",
)
LOOP_A: tuple[str, ...] = ("O", "Q", "E", "D", "X", "R")
LOOP_B: tuple[str, ...] = ("V", "RR")
RS_REOPEN_GATES: tuple[str, ...] = ("Q", "E", "D", "X")
RS_INVALIDATE_GATES: frozenset[str] = frozenset({"Q", "E", "D", "X", "R"})
_LEGACY_GATE_IDS: dict[str, str] = {"open": "O"}
GATE_STATUSES = frozenset({"pending", "active", "closed", "invalidated"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_gate_entry(*, status: str) -> dict[str, Any]:
    return {"status": status, "closed_at": None}


def init_gate_state(*, cycle_id: str, stage: str) -> dict[str, Any]:
    gates: dict[str, dict[str, Any]] = {}
    for gate in GATE_ORDER:
        gates[gate] = _default_gate_entry(status="pending")
    gates["O"] = _default_gate_entry(status="active")
    return normalize_gate_state(
        {
            "version": "1",
            "cycle_id": cycle_id,
            "stage": stage,
            "active_gate": "O",
            "gates": gates,
            "skipped_gates": [],
            "updated_at": _now_iso(),
        }
    )


def validate_gate_state(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r}")

    active = str(data.get("active_gate", ""))
    if active not in GATE_ORDER:
        errors.append(f"invalid active_gate: {active!r}")

    gates = data.get("gates")
    if not isinstance(gates, dict):
        errors.append("gates must be an object")
        return errors

    for gate in GATE_ORDER:
        entry = gates.get(gate)
        if not isinstance(entry, dict):
            errors.append(f"gates.{gate} must be an object")
            continue
        status = str(entry.get("status", "")).lower()
        if status not in GATE_STATUSES:
            errors.append(f"gates.{gate}.status invalid: {status!r}")

    if active and isinstance(gates, dict):
        active_entry = gates.get(active)
        if isinstance(active_entry, dict):
            active_status = str(active_entry.get("status", "")).lower()
            terminal_closed = active == "DC" and active_status == "closed"
            if active_status != "active" and not terminal_closed:
                errors.append(
                    f"active_gate {active!r} must have status active, got {active_status!r}"
                )

    return errors


def _migrate_legacy_gate_ids(data: dict[str, Any]) -> dict[str, Any]:
    """Map pre-O gate id ``open`` to ``O`` on read."""
    updated = dict(data)
    active = str(updated.get("active_gate", ""))
    if active in _LEGACY_GATE_IDS:
        updated["active_gate"] = _LEGACY_GATE_IDS[active]
    gates_raw = updated.get("gates")
    if isinstance(gates_raw, dict):
        gates = dict(gates_raw)
        if "open" in gates:
            if "O" not in gates:
                gates["O"] = gates["open"]
            del gates["open"]
        updated["gates"] = gates
    return updated


def normalize_gate_state(data: dict[str, Any]) -> dict[str, Any]:
    data = _migrate_legacy_gate_ids(data)
    gates_raw = data.get("gates")
    gates: dict[str, dict[str, Any]] = {}
    if isinstance(gates_raw, dict):
        for gate in GATE_ORDER:
            entry = gates_raw.get(gate, {})
            if not isinstance(entry, dict):
                entry = {}
            status = str(entry.get("status", "pending")).lower()
            if status not in GATE_STATUSES:
                status = "pending"
            gates[gate] = {
                "status": status,
                "closed_at": entry.get("closed_at"),
            }
    else:
        for gate in GATE_ORDER:
            gates[gate] = _default_gate_entry(status="pending")

    active = str(data.get("active_gate", "O"))
    if active not in GATE_ORDER:
        active = "O"

    return {
        "version": "1",
        "cycle_id": str(data.get("cycle_id", "")),
        "stage": str(data.get("stage", "")),
        "active_gate": active,
        "gates": gates,
        "skipped_gates": list(data.get("skipped_gates") or []),
        "updated_at": data.get("updated_at") or _now_iso(),
    }


def load_gate_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"gate-state not found: {path}")
    data = _migrate_legacy_gate_ids(json.loads(path.read_text(encoding="utf-8")))
    errors = validate_gate_state(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_gate_state(data)


def save_gate_state(path: Path, data: dict[str, Any]) -> None:
    normalized = normalize_gate_state(data)
    errors = validate_gate_state(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized["updated_at"] = _now_iso()
    atomic_write_text(
        path,
        json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
    )


def gate_index(gate: str) -> int:
    return GATE_ORDER.index(gate)


def downstream_gates(gate: str) -> tuple[str, ...]:
    idx = gate_index(gate)
    return GATE_ORDER[idx:]


def is_gate_closed(state: dict[str, Any], gate: str) -> bool:
    entry = state["gates"].get(gate, {})
    return str(entry.get("status", "")).lower() == "closed"


def close_gate(state: dict[str, Any], gate: str) -> dict[str, Any]:
    updated = normalize_gate_state(state)
    gates = updated["gates"]
    gates[gate]["status"] = "closed"
    gates[gate]["closed_at"] = _now_iso()
    idx = gate_index(gate)
    if idx + 1 < len(GATE_ORDER):
        next_gate = GATE_ORDER[idx + 1]
        gates[next_gate]["status"] = "active"
        updated["active_gate"] = next_gate
    else:
        updated["active_gate"] = gate
    updated["updated_at"] = _now_iso()
    return updated


def activate_gate(state: dict[str, Any], gate: str) -> dict[str, Any]:
    updated = normalize_gate_state(state)
    for g in GATE_ORDER:
        entry = updated["gates"][g]
        if g == gate:
            entry["status"] = "active"
        elif str(entry.get("status", "")).lower() == "active":
            entry["status"] = "closed" if g == "O" else "pending"
    updated["active_gate"] = gate
    updated["updated_at"] = _now_iso()
    return updated


def invalidate_from_gate(state: dict[str, Any], gate: str) -> dict[str, Any]:
    updated = normalize_gate_state(state)
    for g in downstream_gates(gate):
        entry = updated["gates"][g]
        if g == gate:
            entry["status"] = "active"
        else:
            entry["status"] = "invalidated"
        entry["closed_at"] = None
    updated["active_gate"] = gate
    updated["skipped_gates"] = []
    updated["updated_at"] = _now_iso()
    return updated


def close_gate_r(state: dict[str, Any], *, exit_path: str) -> dict[str, Any]:
    """Close R and route to Loop B (V) or directly to DC."""
    if exit_path not in {"loop_b", "dc"}:
        raise ValueError(f"invalid R exit_path: {exit_path!r}")
    updated = close_gate(state, "R")
    if exit_path == "dc":
        updated["gates"]["V"]["status"] = "pending"
        updated["gates"]["V"]["closed_at"] = None
        updated["gates"]["RR"]["status"] = "pending"
        updated["gates"]["RR"]["closed_at"] = None
        updated["gates"]["DC"]["status"] = "active"
        updated["active_gate"] = "DC"
        updated["skipped_gates"] = ["V", "RR"]
    else:
        updated["skipped_gates"] = []
    updated["updated_at"] = _now_iso()
    return updated


def close_gate_v(state: dict[str, Any], *, exit_path: str) -> dict[str, Any]:
    if exit_path not in {"rr", "dc"}:
        raise ValueError(f"invalid V exit_path: {exit_path!r}")
    updated = close_gate(state, "V")
    if exit_path == "dc":
        updated["gates"]["RR"]["status"] = "pending"
        updated["gates"]["RR"]["closed_at"] = None
        updated["gates"]["DC"]["status"] = "active"
        updated["active_gate"] = "DC"
        skipped = list(updated.get("skipped_gates") or [])
        if "RR" not in skipped:
            skipped.append("RR")
        updated["skipped_gates"] = skipped
    return updated


def close_gate_rr(state: dict[str, Any], *, exit_path: str) -> dict[str, Any]:
    if exit_path not in {"dc", "return_r"}:
        raise ValueError(f"invalid RR exit_path: {exit_path!r}")
    if exit_path == "return_r":
        return reactivate_gate_for_r_rerun(state)
    return close_gate(state, "RR")


def reactivate_gate_for_r_rerun(state: dict[str, Any]) -> dict[str, Any]:
    """RR exit 2: return to R without invalidating LoopA."""
    updated = normalize_gate_state(state)
    updated["gates"]["R"]["status"] = "active"
    updated["gates"]["R"]["closed_at"] = None
    for gate in ("V", "RR", "DC"):
        updated["gates"][gate]["status"] = "pending"
        updated["gates"][gate]["closed_at"] = None
    updated["active_gate"] = "R"
    updated["skipped_gates"] = []
    updated["updated_at"] = _now_iso()
    return updated


def header_gate_symbols(state: dict[str, Any]) -> dict[str, str]:
    symbols: dict[str, str] = {}
    for gate in ("O", "Q", "E", "D", "X", "R", "V", "RR", "DC"):
        status = str(state["gates"].get(gate, {}).get("status", "pending")).lower()
        symbols[gate] = "✅" if status == "closed" else "⬜"
    return symbols
