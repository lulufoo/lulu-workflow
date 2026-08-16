#!/usr/bin/env python3
"""Schema and I/O for inductive-gate-state.json.

Tracks the G1–G4 lock machine. After G4 closes, active_gate becomes
complete. Retired active_gate=G5 is incompatible and is not translated
to complete.

Gate statuses: pending | active | closed | reopened
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

GATE_ORDER: tuple[str, ...] = ("G1", "G2", "G3", "G4")
COMPLETE_GATE = "complete"
ROUTING_GATES: tuple[str, ...] = GATE_ORDER + (COMPLETE_GATE,)
_RETIRED_G5 = "G5"
GATE_STATUSES = frozenset({"pending", "active", "closed", "reopened"})

_GATE_LABELS: dict[str, str] = {
    "G1": "Shape Perception",
    "G2": "Topic Loop",
    "G3": "Open-point Loop",
    "G4": "Internal Audit",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_gate_entry(*, status: str) -> dict[str, Any]:
    return {"status": status, "closed_at": None, "payload": None}


def init_gate_state(
    *,
    cycle_id: str,
    stage: str,
    master_conversation_id: str = "",
) -> dict[str, Any]:
    """Return a new gate state with G1 active."""
    gates: dict[str, dict[str, Any]] = {}
    for gate in GATE_ORDER:
        status = "active" if gate == "G1" else "pending"
        gates[gate] = _default_gate_entry(status=status)
    data: dict[str, Any] = {
        "version": "1",
        "cycle_id": cycle_id,
        "stage": stage,
        "active_gate": "G1",
        "gates": gates,
        "updated_at": _now_iso(),
    }
    if master_conversation_id.strip():
        data["master_conversation_id"] = master_conversation_id.strip()
    return normalize_gate_state(data)


def validate_gate_state(data: dict[str, Any]) -> list[str]:
    """Return validation error strings (empty list = valid)."""
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r}")

    active = str(data.get("active_gate", ""))
    if active == _RETIRED_G5:
        errors.append("incompatible: active_gate G5 is retired")
    elif active not in ROUTING_GATES:
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

    if active == COMPLETE_GATE:
        for gate in GATE_ORDER:
            entry = gates.get(gate) if isinstance(gates, dict) else None
            if not isinstance(entry, dict) or str(entry.get("status", "")).lower() != "closed":
                errors.append(f"active_gate complete requires gates.{gate}.status=closed")
    elif active and active != _RETIRED_G5 and isinstance(gates, dict):
        active_entry = gates.get(active)
        if isinstance(active_entry, dict):
            active_status = str(active_entry.get("status", "")).lower()
            if active_status not in {"active", "reopened"}:
                errors.append(
                    f"active_gate {active!r} must have status active or reopened, "
                    f"got {active_status!r}"
                )

    return errors


def normalize_gate_state(data: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized gate state dict."""
    gates_raw = data.get("gates") or {}
    gates: dict[str, dict[str, Any]] = {}
    for gate in GATE_ORDER:
        entry = dict(gates_raw.get(gate) or {})
        status = str(entry.get("status", "pending")).lower()
        if status not in GATE_STATUSES:
            status = "pending"
        gates[gate] = {
            "status": status,
            "closed_at": entry.get("closed_at"),
            "payload": entry.get("payload"),
        }

    active = str(data.get("active_gate", "G1"))
    if active == _RETIRED_G5:
        active = _RETIRED_G5
    elif active not in ROUTING_GATES:
        active = "G1"

    normalized: dict[str, Any] = {
        "version": "1",
        "cycle_id": str(data.get("cycle_id", "")),
        "stage": str(data.get("stage", "")),
        "active_gate": active,
        "gates": gates,
        "updated_at": data.get("updated_at") or _now_iso(),
    }
    master = str(data.get("master_conversation_id", "")).strip()
    if master:
        normalized["master_conversation_id"] = master
    return normalized


def load_gate_state(path: Path) -> dict[str, Any]:
    """Load, validate, and normalize gate state from disk."""
    if not path.exists():
        raise FileNotFoundError(f"inductive-gate-state not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_gate_state(data)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_gate_state(data)


def save_gate_state(path: Path, data: dict[str, Any]) -> None:
    """Validate, normalize, and write gate state to disk."""
    normalized = normalize_gate_state(data)
    errors = validate_gate_state(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    normalized["updated_at"] = _now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(normalized, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def gate_index(gate: str) -> int:
    return GATE_ORDER.index(gate)


def routing_index(active: str) -> int:
    """Index of the current routing position. complete sits after G4."""
    if active == COMPLETE_GATE:
        return len(GATE_ORDER)
    if active in GATE_ORDER:
        return GATE_ORDER.index(active)
    return -1


def is_gate_closed(state: dict[str, Any], gate: str) -> bool:
    entry = state["gates"].get(gate, {})
    return str(entry.get("status", "")).lower() == "closed"


def close_gate(
    state: dict[str, Any], gate: str, *, payload: Any = None
) -> dict[str, Any]:
    """Close a gate, record its payload, and activate the next gate."""
    updated = normalize_gate_state(state)
    gates = updated["gates"]
    gates[gate]["status"] = "closed"
    gates[gate]["closed_at"] = _now_iso()
    if payload is not None:
        gates[gate]["payload"] = payload

    idx = gate_index(gate)
    if idx + 1 < len(GATE_ORDER):
        next_gate = GATE_ORDER[idx + 1]
        gates[next_gate]["status"] = "active"
        updated["active_gate"] = next_gate
    else:
        updated["active_gate"] = COMPLETE_GATE

    updated["updated_at"] = _now_iso()
    return updated


def reopen_gate(state: dict[str, Any], gate: str) -> dict[str, Any]:
    """Reopen a gate (e.g. G4 audit failure -> reopen G3).

    Sets target gate to 'reopened'; downstream gates reset to pending.
    """
    updated = normalize_gate_state(state)
    gates = updated["gates"]
    target_idx = gate_index(gate)

    for idx, g in enumerate(GATE_ORDER):
        if idx < target_idx:
            pass  # upstream gates stay closed
        elif g == gate:
            gates[g]["status"] = "reopened"
            gates[g]["closed_at"] = None
        else:
            gates[g]["status"] = "pending"
            gates[g]["closed_at"] = None

    updated["active_gate"] = gate
    updated["updated_at"] = _now_iso()
    return updated


def header_gate_symbols(state: dict[str, Any]) -> dict[str, str]:
    """Return display symbols per gate for session headers."""
    symbols: dict[str, str] = {}
    for gate in GATE_ORDER:
        status = str(state["gates"].get(gate, {}).get("status", "pending")).lower()
        label = _GATE_LABELS.get(gate, gate)
        symbols[gate] = f"closed {label}" if status == "closed" else f"pending {label}"
    return symbols
