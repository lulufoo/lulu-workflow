#!/usr/bin/env python3
"""Schema and I/O for decision gate-state.json."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dec_io import atomic_write_text

GATE_ORDER: tuple[str, ...] = (
    "O",
    "Q",
    "GL",
    "E",
    "D",
    "X",
    "R",
    "DC",
)
LOOP_A: tuple[str, ...] = ("O", "Q", "GL", "E", "D", "X", "R")
LOOP_B: tuple[str, ...] = ()
# Retired spine id; legacy sessions may still have active_gate=RR (hard-fail on use).
_LEGACY_SPINE_V = "V"
_LEGACY_GATE_RR = "RR"
LEGACY_RR_ACTIVE_ERROR = (
    "legacy gate RR is active; re-run R (RR retired — use R handle + complete-assumption)"
)
# Align-from gates for Realign (formerly "reopen"); letter code RS = Realign State.
# Spine id GL (Grill) — not protocol P/S3 and not RS metavariable "G".
RS_REALIGN_GATES: tuple[str, ...] = ("Q", "GL", "E", "D", "X")
# Backward-compatible alias while callers migrate.
RS_REOPEN_GATES: tuple[str, ...] = RS_REALIGN_GATES
_LEGACY_GATE_IDS: dict[str, str] = {"open": "O"}
GATE_STATUSES = frozenset({"pending", "active", "closed", "stale", "invalidated"})
# active_gate may be in progress (active) or awaiting Realign update (stale).
_ACTIVE_GATE_STATUSES = frozenset({"active", "stale"})
_REACHED_GATE_STATUSES = frozenset({"active", "stale", "closed"})


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
    if active == _LEGACY_GATE_RR:
        errors.append(LEGACY_RR_ACTIVE_ERROR)
        return errors
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
            if active_status not in _ACTIVE_GATE_STATUSES and not terminal_closed:
                errors.append(
                    f"active_gate {active!r} must have status active or stale, "
                    f"got {active_status!r}"
                )

    return errors


def _migrate_legacy_gate_ids(data: dict[str, Any]) -> dict[str, Any]:
    """Map pre-O gate id ``open`` to ``O``; fold retired spine ``V`` onto ``R``."""
    updated = dict(data)
    active = str(updated.get("active_gate", ""))
    if active in _LEGACY_GATE_IDS:
        updated["active_gate"] = _LEGACY_GATE_IDS[active]
        active = str(updated["active_gate"])
    gates_raw = updated.get("gates")
    if isinstance(gates_raw, dict):
        gates = dict(gates_raw)
        if "open" in gates:
            if "O" not in gates:
                gates["O"] = gates["open"]
            del gates["open"]
        v_entry = gates.pop(_LEGACY_SPINE_V, None)
        if isinstance(v_entry, dict):
            v_status = str(v_entry.get("status", "pending")).lower()
            r_entry = gates.get("R")
            if not isinstance(r_entry, dict):
                r_entry = _default_gate_entry(status="pending")
            r_status = str(r_entry.get("status", "pending")).lower()
            if active == _LEGACY_SPINE_V or (
                v_status in {"active", "stale"} and r_status == "pending"
            ):
                gates["R"] = {
                    "status": "stale" if v_status == "stale" else "active",
                    "closed_at": None,
                }
                updated["active_gate"] = "R"
            elif v_status == "closed" and r_status == "pending":
                gates["R"] = {"status": "active", "closed_at": None}
                if active in {_LEGACY_SPINE_V, "R"}:
                    updated["active_gate"] = "R"
        updated["gates"] = gates
    skipped = updated.get("skipped_gates")
    if isinstance(skipped, list):
        updated["skipped_gates"] = [
            g for g in skipped if g not in {_LEGACY_SPINE_V, _LEGACY_GATE_RR}
        ]
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
    if active == _LEGACY_SPINE_V:
        active = "R"
    if active not in GATE_ORDER and active != _LEGACY_GATE_RR:
        active = "O"

    gl_status = str(gates["GL"].get("status", "pending")).lower()
    if gl_status == "pending":
        later_reached = any(
            str(gates[g].get("status", "pending")).lower() in {"closed", "active", "stale"}
            for g in ("E", "D", "X", "R", "DC")
        )
        if later_reached or active in {"E", "D", "X", "R", "DC"}:
            gates["GL"] = {"status": "closed", "closed_at": gates["GL"].get("closed_at")}

    result = {
        "version": "1",
        "cycle_id": str(data.get("cycle_id", "")),
        "stage": str(data.get("stage", "")),
        "active_gate": active,
        "gates": gates,
        "skipped_gates": list(data.get("skipped_gates") or []),
        "updated_at": data.get("updated_at") or _now_iso(),
    }
    resume = str(data.get("resume_gate") or "").strip()
    if (
        resume in RS_REALIGN_GATES
        and str(gates.get(resume, {}).get("status", "")).lower() == "stale"
    ):
        result["resume_gate"] = resume
    return result


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


def is_gate_reached(state: dict[str, Any], gate: str) -> bool:
    """Return whether a gate has been reached, including stale Realign state."""
    entry = state["gates"].get(gate, {})
    return str(entry.get("status", "")).lower() in _REACHED_GATE_STATUSES


def _focus_next_gate(gates: dict[str, dict[str, Any]], next_gate: str) -> None:
    """Advance focus to next_gate without wiping an existing stale mark."""
    if str(gates[next_gate].get("status", "")).lower() != "stale":
        gates[next_gate]["status"] = "active"


def close_gate(state: dict[str, Any], gate: str) -> dict[str, Any]:
    updated = normalize_gate_state(state)
    gates = updated["gates"]
    gates[gate]["status"] = "closed"
    gates[gate]["closed_at"] = _now_iso()
    idx = gate_index(gate)
    if idx + 1 < len(GATE_ORDER):
        next_gate = GATE_ORDER[idx + 1]
        _focus_next_gate(gates, next_gate)
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
            if str(entry.get("status", "")).lower() != "stale":
                entry["status"] = "active"
        elif str(entry.get("status", "")).lower() == "active":
            entry["status"] = "closed" if g == "O" else "pending"
    updated["active_gate"] = gate
    updated["updated_at"] = _now_iso()
    return updated


def _select_resume_gate(state: dict[str, Any]) -> str | None:
    """Pick the in-progress align gate, or keep a marker that is still stale.

    Call before the sweep. Closed gates become stale during the sweep and must
    not be chosen from that later status.
    """
    gates = state.get("gates") or {}
    active = str(state.get("active_gate", ""))
    active_entry = gates.get(active)
    active_status = ""
    if isinstance(active_entry, dict):
        active_status = str(active_entry.get("status", "")).lower()
    if active in RS_REALIGN_GATES and active_status == "active":
        return active
    previous = str(state.get("resume_gate") or "")
    prev_entry = gates.get(previous)
    if previous in RS_REALIGN_GATES and isinstance(prev_entry, dict):
        if str(prev_entry.get("status", "")).lower() == "stale":
            return previous
    return None


def mark_stale_from_gate(state: dict[str, Any], gate: str) -> dict[str, Any]:
    """Mark align gate G and reached downstream as stale; never-reached pending left alone.

    Does not delete gate-payloads. Session Realign path is update-only.
    """
    if gate not in GATE_ORDER:
        raise ValueError(f"invalid gate: {gate!r}")
    updated = normalize_gate_state(state)
    resume = _select_resume_gate(updated)
    for g in downstream_gates(gate):
        entry = updated["gates"][g]
        status = str(entry.get("status", "")).lower()
        if g == gate:
            entry["status"] = "stale"
            entry["closed_at"] = None
            continue
        if status == "pending":
            continue
        entry["status"] = "stale"
        entry["closed_at"] = None
    if resume and str(updated["gates"][resume].get("status", "")).lower() == "stale":
        updated["resume_gate"] = resume
    else:
        updated.pop("resume_gate", None)
    updated["active_gate"] = gate
    updated["skipped_gates"] = []
    updated["updated_at"] = _now_iso()
    return updated


def invalidate_from_gate(state: dict[str, Any], gate: str) -> dict[str, Any]:
    """Removed: session Realign no longer destroys downstream. Use mark_stale_from_gate."""
    raise ValueError(
        "invalidate_from_gate is removed; use mark_stale_from_gate / rs-commit (stale sweep)"
    )


def close_gate_r(state: dict[str, Any], *, exit_path: str) -> dict[str, Any]:
    """Close R and route to DC (``dc``) or keep R active (``human_decision``)."""
    if exit_path not in {"dc", "human_decision"}:
        raise ValueError(f"invalid R exit_path: {exit_path!r}")
    if exit_path == "human_decision":
        return normalize_gate_state(state)
    return close_gate(state, "R")


def reactivate_gate_for_r_rerun(state: dict[str, Any]) -> dict[str, Any]:
    """Retired: RR return_r removed."""
    raise ValueError("reactivate_gate_for_r_rerun removed; RR retired")


def header_gate_symbols(state: dict[str, Any]) -> dict[str, str]:
    symbols: dict[str, str] = {}
    for gate in ("O", "Q", "GL", "E", "D", "X", "R", "DC"):
        status = str(state["gates"].get(gate, {}).get("status", "pending")).lower()
        symbols[gate] = "✅" if status == "closed" else "⬜"
    return symbols
