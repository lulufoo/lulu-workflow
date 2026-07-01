#!/usr/bin/env python3
"""Inductive runner outer gate spine control.

Manages the G1->G2->G3->G4 gate state machine for the inductive runner.
Delegates all G3 section / EP operations to inductive_section_control.py
via subprocess ($INDUCTIVE_SECTION_CTL).

Subcommands:
    init-session        Seed gate state + delegate init-pointer to section control
    resolve-context     Return active_gate, active_section, open-EP count,
                        architecture_view summary (multi-turn resume entry point)
    gate-close          Close a gate with payload validation and prereq check

Payload per gate:
    G1: {"architecture_view": {...}, "shape_constraints": [...]}
    G2: {}  (automatic close; no user payload required)
    G3: must pass check-coverage (delegated to section control)
    G4: {"reforms_shape": bool, "shape_absorbed": bool, "conflicts": [...],
         "buildable": bool, "reversible": bool, "verifiable": bool}

All subcommands print JSON to stdout and exit 0 on success, exit 1 on failure.

Global flag: --out-dir PATH (required for all subcommands)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from inductive_gate_state_schema import (  # noqa: E402
    GATE_ORDER,
    close_gate,
    header_gate_symbols,
    init_gate_state,
    is_gate_closed,
    load_gate_state,
    reopen_gate,
    save_gate_state,
)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _gate_state_path(out_dir: Path) -> Path:
    return out_dir / "inductive-gate-state.json"


def _dqi_path(out_dir: Path) -> Path:
    return out_dir / "inductive-dqi.json"


def _section_ctl(out_dir: Path) -> list[str]:
    """Return the base argv for invoking inductive_section_control.py."""
    script = _HERE / "inductive_section_control.py"
    return [sys.executable, str(script), "--out-dir", str(out_dir)]


def _run_section_ctl(out_dir: Path, *extra_args: str) -> dict[str, Any]:
    """Run section control subcommand and return parsed JSON stdout."""
    cmd = _section_ctl(out_dir) + list(extra_args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": result.stdout or result.stderr}


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _ok(payload: dict[str, Any]) -> None:
    print(json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False))


def _fail(message: str) -> None:
    print(json.dumps({"ok": False, "error": message}, indent=2, ensure_ascii=False))
    sys.exit(1)


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------

def cmd_init_session(out_dir: Path, args: argparse.Namespace) -> None:
    gate_path = _gate_state_path(out_dir)
    if gate_path.exists():
        _fail(f"gate state already exists: {gate_path}; use resolve-context to resume")

    cycle_id = args.cycle_id or ""
    stage = args.stage or ""
    state = init_gate_state(cycle_id=cycle_id, stage=stage)
    save_gate_state(gate_path, state)

    # Delegate section pointer + EP ledger init
    sections: str = args.sections or ""
    mandatory: str = args.mandatory or ""

    ptr_result = _run_section_ctl(
        out_dir,
        "init-pointer",
        "--sections", sections,
        "--mandatory", mandatory,
        "--cycle-id", cycle_id,
    )
    if not ptr_result.get("ok"):
        _fail("section pointer init failed: " + ptr_result.get("error", "unknown"))

    _ok({
        "message": "session initialized",
        "active_gate": "G1",
        "sections": sections,
        "mandatory": mandatory,
    })


def cmd_resolve_context(out_dir: Path, _args: argparse.Namespace) -> None:
    """Multi-turn resume entry point: aggregate gate + section state."""
    gate_path = _gate_state_path(out_dir)
    if not gate_path.exists():
        _fail("gate state not found; run init-session first")

    state = load_gate_state(gate_path)
    symbols = header_gate_symbols(state)

    section_status: dict[str, Any] = {}
    frontier: dict[str, Any] = {}
    active_section = None
    open_ep_count = 0

    if state["active_gate"] in {"G3", "G4"}:
        sec_result = _run_section_ctl(out_dir, "status")
        if sec_result.get("ok"):
            section_status = sec_result.get("sections", {})
            frontier = sec_result.get("frontier", {})
            active_section = sec_result.get("active_section")
            open_ep_count = sec_result.get("open_blocking_ep_count", 0)

    architecture_view = None
    dqi_p = _dqi_path(out_dir)
    if dqi_p.exists():
        try:
            dqi = json.loads(dqi_p.read_text(encoding="utf-8"))
            architecture_view = dqi.get("architecture_view")
        except Exception:
            pass

    _ok({
        "active_gate": state["active_gate"],
        "gate_symbols": symbols,
        "gates": {g: state["gates"][g]["status"] for g in GATE_ORDER},
        "active_section": active_section,
        "section_statuses": section_status,
        "frontier": frontier,
        "open_blocking_ep_count": open_ep_count,
        "architecture_view": architecture_view,
    })


def cmd_gate_close(out_dir: Path, args: argparse.Namespace) -> None:
    gate: str = args.gate.upper()
    if gate not in GATE_ORDER:
        _fail(f"invalid gate: {gate!r}; must be one of {GATE_ORDER}")

    gate_path = _gate_state_path(out_dir)
    if not gate_path.exists():
        _fail("gate state not found; run init-session first")

    state = load_gate_state(gate_path)

    # Guard: gate must be the current active gate
    if state.get("active_gate") != gate:
        _fail(
            f"cannot close gate {gate!r}: active gate is {state.get('active_gate')!r}; "
            "switch to the correct gate first or call gate-reopen to reset"
        )

    # Guard: gate must not already be closed
    if is_gate_closed(state, gate):
        _fail(f"gate {gate!r} is already closed")

    # Prereq: all previous gates must be closed
    idx = GATE_ORDER.index(gate)
    for prev in GATE_ORDER[:idx]:
        if not is_gate_closed(state, prev):
            _fail(f"prereq not met: gate {prev!r} must be closed before closing {gate!r}")

    # Parse payload
    payload: dict[str, Any] = {}
    if args.payload:
        try:
            payload = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            _fail(f"invalid payload JSON: {exc}")

    # Gate-specific validation
    if gate == "G1":
        _validate_g1_payload(payload)
    elif gate == "G3":
        _validate_g3_close(out_dir)
    elif gate == "G4":
        _validate_g4_payload(out_dir, payload)

    # Close the gate and persist
    updated = close_gate(state, gate, payload=payload if payload else None)
    save_gate_state(gate_path, updated)

    # For G1: write architecture_view to DQI
    if gate == "G1" and payload.get("architecture_view"):
        _write_dqi_field(out_dir, "architecture_view", payload["architecture_view"])
        _write_dqi_field(out_dir, "shape_constraints", payload.get("shape_constraints", []))

    # For G4: write recompose_check to DQI
    if gate == "G4":
        _write_dqi_field(out_dir, "recompose_check", payload)

    _ok({
        "closed": gate,
        "active_gate": updated["active_gate"],
    })


# ---------------------------------------------------------------------------
# Gate-specific payload validators
# ---------------------------------------------------------------------------

def _validate_g1_payload(payload: dict[str, Any]) -> None:
    if not payload.get("architecture_view"):
        _fail("G1 payload must include 'architecture_view'")
    av = payload["architecture_view"]
    required = ("as_is", "to_be", "scope", "spine", "traces_to")
    missing = [f for f in required if not av.get(f)]
    if missing:
        _fail(f"architecture_view missing fields: {missing}")


def _validate_g3_close(out_dir: Path) -> None:
    cov_result = _run_section_ctl(out_dir, "check-coverage")
    if not cov_result.get("ok"):
        errors = cov_result.get("errors") or [cov_result.get("error", "coverage check failed")]
        _fail("G3 coverage predicate not met: " + "; ".join(str(e) for e in errors))


def _validate_g4_payload(out_dir: Path, payload: dict[str, Any]) -> None:
    required_bool = ("reforms_shape", "shape_absorbed", "buildable", "reversible", "verifiable")
    missing = [f for f in required_bool if payload.get(f) is None]
    if missing:
        _fail(f"G4 payload missing fields: {missing}")

    if not payload.get("reforms_shape"):
        _fail("G4 gate-close rejected: reforms_shape=false; reopen G1 to correct shape")

    if not payload.get("shape_absorbed"):
        _fail("G4 gate-close rejected: shape_absorbed=false; rewind affected sections")

    conflicts = payload.get("conflicts") or []
    if conflicts:
        _fail(
            f"G4 gate-close rejected: {len(conflicts)} conflict(s) unresolved; "
            "rewind affected sections to resolve"
        )


# ---------------------------------------------------------------------------
# DQI I/O
# ---------------------------------------------------------------------------

def _write_dqi_field(out_dir: Path, field: str, value: Any) -> None:
    """Merge a field into inductive-dqi.json (create if missing)."""
    dqi_p = _dqi_path(out_dir)
    if dqi_p.exists():
        try:
            dqi = json.loads(dqi_p.read_text(encoding="utf-8"))
        except Exception:
            dqi = {}
    else:
        dqi = {"version": "1"}

    dqi[field] = value

    dqi_p.parent.mkdir(parents=True, exist_ok=True)
    with dqi_p.open("w", encoding="utf-8") as fh:
        json.dump(dqi, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def cmd_gate_reopen(out_dir: Path, args: argparse.Namespace) -> None:
    """Reopen a gate that was previously closed (e.g. G4 audit failure → reopen G3).

    Sets the target gate to 'reopened' and resets all downstream gates to 'pending'.
    The active_gate is moved back to the target gate so gate-close can be called
    again after the issue is resolved.
    """
    gate: str = args.gate.upper()
    if gate not in GATE_ORDER:
        _fail(f"invalid gate: {gate!r}; must be one of {GATE_ORDER}")

    gate_path = _gate_state_path(out_dir)
    if not gate_path.exists():
        _fail("gate state not found; run init-session first")

    state = load_gate_state(gate_path)
    current_active = state.get("active_gate", "")

    target_idx = GATE_ORDER.index(gate)
    active_idx = GATE_ORDER.index(current_active) if current_active in GATE_ORDER else -1

    # Can only reopen a gate that has been reached (active_gate >= target)
    if active_idx < target_idx:
        _fail(
            f"cannot reopen gate {gate!r}: it has not been reached yet "
            f"(active_gate={current_active!r})"
        )

    # No-op if the gate is already open/active/reopened
    if active_idx == target_idx and not is_gate_closed(state, gate):
        _fail(
            f"gate {gate!r} is already active or reopened — nothing to reopen"
        )

    updated = reopen_gate(state, gate)
    save_gate_state(gate_path, updated)

    _ok({
        "reopened": gate,
        "active_gate": updated["active_gate"],
        "note": (
            "downstream gates reset to pending; "
            "resolve the issue then call gate-close again"
        ),
    })


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        metavar="PATH",
        help="$INDUCTIVE_OUT_DIR: directory for inductive state files and artifacts",
    )

    sub = parser.add_subparsers(dest="subcommand", required=True)

    # init-session
    p = sub.add_parser("init-session", help="Seed gate state + section pointer")
    p.add_argument("--sections", required=True, help="Comma-separated coverage_sections")
    p.add_argument("--mandatory", default="", help="Comma-separated mandatory section keys")
    p.add_argument("--cycle-id", default="", help="Cycle id for traceability")
    p.add_argument("--stage", default="", help="Compose stage id (e.g. lulu-design)")

    # resolve-context
    sub.add_parser(
        "resolve-context",
        help="Return active_gate, active_section, open-EP count (multi-turn resume entry)",
    )

    # gate-close
    p = sub.add_parser("gate-close", help="Close a gate with payload validation")
    p.add_argument("--gate", required=True, metavar="G", help="G1 | G2 | G3 | G4")
    p.add_argument(
        "--payload",
        default="{}",
        metavar="JSON",
        help="Gate-specific close payload (JSON object)",
    )

    # gate-reopen
    p = sub.add_parser(
        "gate-reopen",
        help="Reopen a previously closed gate (e.g. G4 audit failure → reopen G3)",
    )
    p.add_argument(
        "--gate",
        required=True,
        metavar="G",
        help="G1 | G2 | G3 | G4 — gate to reopen; downstream gates reset to pending",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    dispatch = {
        "init-session": cmd_init_session,
        "resolve-context": cmd_resolve_context,
        "gate-close": cmd_gate_close,
        "gate-reopen": cmd_gate_reopen,
    }

    handler = dispatch.get(args.subcommand)
    if handler is None:
        _fail(f"unknown subcommand: {args.subcommand!r}")

    handler(out_dir, args)


if __name__ == "__main__":
    main()
