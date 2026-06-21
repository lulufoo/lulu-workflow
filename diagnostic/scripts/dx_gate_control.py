#!/usr/bin/env python3
"""Gate state machine control for diagnostic sessions.

Subcommands:
    init-session           Bootstrap gate-state, registers, and decision-doc skeleton
    resolve-context        JSON context for runners and Reply Header rendering
    gate-activate          Activate a gate (e.g. open → Q)
    gate-close             Close active gate, patch decision-doc, advance pointer
    invalidate-from        RS mechanical invalidation from a gate downstream
    check-delivery-ready   Validate decision-doc + gates for DC delivery
    deliver                Set session-state Delivered (requires DC closed)
    migrate-session        Bootstrap gate-state/registers for legacy sessions
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from fetch_template import fetch_template  # noqa: E402

from dx_decision_doc_schema import (  # noqa: E402
    GATE_CLOSE_PREREQ,
    check_decision_doc_ready,
    clear_sections_downstream,
    init_decision_doc,
    load_decision_doc,
    render_decision_rationale_body,
    render_direction_body,
    render_execution_analysis_body,
    render_problem_body,
    render_scope_body,
    replace_section,
    save_decision_doc,
)
from dx_domain_constraints_schema import (  # noqa: E402
    active_x_dimensions,
    is_x_dimension_active,
    load_domain_constraints,
    load_stage_defaults,
    merge_domain_constraints,
    save_domain_constraints,
)
from dx_gate_state_schema import (  # noqa: E402
    GATE_ORDER,
    LOOP_A,
    activate_gate,
    close_gate,
    close_gate_r,
    close_gate_rr,
    close_gate_v,
    init_gate_state,
    invalidate_from_gate,
    is_gate_closed,
    load_gate_state,
    save_gate_state,
)
from dx_register_schema import (  # noqa: E402
    RISK_LEVELS,
    init_registers,
    load_registers,
    save_registers,
)
from dx_session_render import render_reply_header  # noqa: E402
from dx_workflow_common import (  # noqa: E402
    decision_doc_path,
    domain_constraints_path,
    gate_state_path,
    registers_path,
    session_base_dir,
    session_state_path,
    write_session_state,
)

from dx_migrate_session import migrate_session_dir, needs_migration  # noqa: E402
from dx_register_control import sync_registers_to_doc  # noqa: E402


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _emit_error(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    return 1


def _paths(project_root: Path, cycle_id: str, stage: str) -> dict[str, Path]:
    base = project_root / session_base_dir(cycle_id, stage)
    return {
        "session_dir": base,
        "gate_state": project_root / gate_state_path(cycle_id, stage),
        "registers": project_root / registers_path(cycle_id, stage),
        "decision_doc": project_root / decision_doc_path(cycle_id, stage),
        "domain_constraints": project_root / domain_constraints_path(cycle_id, stage),
    }


def _load_session_constraints(project_root: Path, cycle_id: str, stage: str) -> dict[str, Any]:
    path = project_root / domain_constraints_path(cycle_id, stage)
    if path.exists():
        return load_domain_constraints(path)
    return load_stage_defaults(project_root, stage)


def _validate_gate_activate_prereqs(state: dict[str, Any], gate: str) -> str | None:
    if gate == "open":
        return "cannot activate open; it is the initial gate"
    if gate == "Q":
        if state["active_gate"] != "open":
            return "gate Q can only be activated from open channel"
        return None
    if gate == "E":
        if not is_gate_closed(state, "Q"):
            return "gate Q must be closed before activating E"
        return None
    prev = {"D": "E", "X": "D", "R": "X", "V": "R", "RR": "V", "DC": "RR"}.get(gate)
    if prev and not is_gate_closed(state, prev):
        return f"gate {prev} must be closed before activating {gate}"
    return None


def _required_prior_gate(gate: str) -> str | None:
    return GATE_CLOSE_PREREQ.get(gate)


def cmd_init_session(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    domain_override: dict[str, Any] | None = None,
) -> int:
    paths = _paths(project_root, cycle_id, stage)
    if paths["gate_state"].exists():
        return _emit_error("gate-state already exists; use a new cycle or remove session dir")

    constraints = load_stage_defaults(project_root, stage)
    if domain_override:
        constraints = merge_domain_constraints(constraints, domain_override)
    save_domain_constraints(paths["domain_constraints"], constraints)

    template = fetch_template(
        "diagnostic",
        "decision_doc_template_url",
        project_root,
    )
    doc = init_decision_doc(template=template, cycle_id=cycle_id, constraints=constraints)
    save_decision_doc(paths["decision_doc"], doc)

    gate_state = init_gate_state(cycle_id=cycle_id, stage=stage)
    save_gate_state(paths["gate_state"], gate_state)

    registers = init_registers(cycle_id=cycle_id, stage=stage)
    save_registers(paths["registers"], registers, r_gate_closed=False)

    sync_registers_to_doc(
        paths["decision_doc"],
        paths["registers"],
        r_gate_closed=False,
        constraints=constraints,
    )

    _emit(
        {
            "ok": True,
            "cycle_id": cycle_id,
            "stage": stage,
            "session_dir": paths["session_dir"].as_posix(),
            "gate_state_path": paths["gate_state"].as_posix(),
            "registers_path": paths["registers"].as_posix(),
            "decision_doc_path": paths["decision_doc"].as_posix(),
            "domain_constraints_path": paths["domain_constraints"].as_posix(),
            "active_gate": gate_state["active_gate"],
            "domain_constraints": constraints,
        }
    )
    return 0


def cmd_resolve_context(project_root: Path, cycle_id: str, stage: str) -> int:
    paths = _paths(project_root, cycle_id, stage)
    try:
        gate_state = load_gate_state(paths["gate_state"])
        r_closed = is_gate_closed(gate_state, "R")
        registers = load_registers(paths["registers"], r_gate_closed=r_closed)
        constraints = _load_session_constraints(project_root, cycle_id, stage)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit(
        {
            "ok": True,
            "cycle_id": cycle_id,
            "stage": stage,
            "session_dir": paths["session_dir"].as_posix(),
            "gate_state_path": paths["gate_state"].as_posix(),
            "registers_path": paths["registers"].as_posix(),
            "decision_doc_path": paths["decision_doc"].as_posix(),
            "domain_constraints_path": paths["domain_constraints"].as_posix(),
            "active_gate": gate_state["active_gate"],
            "gates": gate_state["gates"],
            "skipped_gates": gate_state.get("skipped_gates", []),
            "domain_constraints": constraints,
            "registers": registers,
            "reply_header": render_reply_header(gate_state, registers),
        }
    )
    return 0


_IMPLEMENTED_GATES = frozenset({"Q", "E", "D", "X", "R", "V", "RR", "DC"})

_H_VERIFICATION_PARTS = ("Method:", "Owner:", "Timing:", "Release condition:")


def _validate_gate_close_prereqs(state: dict[str, Any], gate: str) -> str | None:
    if state["active_gate"] != gate:
        return f"active_gate is {state['active_gate']!r}, expected {gate!r}"
    entry = state["gates"].get(gate, {})
    if str(entry.get("status", "")).lower() != "active":
        return f"gate {gate} is not active"

    prior = _required_prior_gate(gate)
    if prior and not is_gate_closed(state, prior):
        return f"gate {prior} must be closed before closing {gate}"
    if gate not in _IMPLEMENTED_GATES:
        return f"gate-close not implemented for gate {gate!r}"
    return None


def _validate_high_risk_verification(verification: str, *, entry_id: str) -> None:
    for part in _H_VERIFICATION_PARTS:
        if part not in verification:
            raise ValueError(f"assumption {entry_id}: High-risk verification missing {part!r}")


def _needs_rr_scope(entry: dict[str, Any]) -> bool:
    risk = str(entry.get("risk", "")).strip()
    if risk == "H":
        return True
    return bool(entry.get("release_tracking"))


def _validate_v_exit_against_registers(
    registers: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    assumptions = registers.get("assumptions", [])
    by_id = {
        str(item.get("id")): item
        for item in payload.get("assumptions", [])
        if isinstance(item, dict)
    }
    reg_ids = {str(entry.get("id")) for entry in assumptions if isinstance(entry, dict)}
    missing = reg_ids - set(by_id)
    if missing:
        raise ValueError(f"missing assumptions in V payload: {sorted(missing)}")

    exit_path = str(payload.get("exit", "")).strip()
    rr_needed = False
    for entry in assumptions:
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id"))
        update = by_id.get(entry_id, {})
        risk = str(update.get("risk", entry.get("risk", ""))).strip()
        release_tracking = bool(update.get("release_tracking", entry.get("release_tracking")))
        merged = {**entry, "risk": risk, "release_tracking": release_tracking}
        if _needs_rr_scope(merged):
            rr_needed = True
        verification = str(update.get("verification", "")).strip()
        if risk == "H" or release_tracking:
            _validate_high_risk_verification(verification, entry_id=entry_id)
        elif risk in {"M", "L"} and verification != "Accepted":
            raise ValueError(f"assumption {entry_id}: Medium/Low verification must be 'Accepted'")

    if exit_path == "dc" and rr_needed:
        raise ValueError("V exit dc requires no High-risk or release-tracking assumptions")
    if exit_path == "rr" and not rr_needed:
        raise ValueError("V exit rr requires at least one High-risk or release-tracking assumption")


def _validate_gate_close_payload(gate: str, payload: dict[str, Any], *, constraints: dict[str, Any]) -> None:
    if gate == "Q":
        if not str(payload.get("problem_statement", "")).strip():
            raise ValueError("problem_statement is required")
        return
    if gate == "E":
        directions = payload.get("directions", [])
        if not isinstance(directions, list) or len(directions) < 2:
            raise ValueError("directions must contain at least 2 items")
        if len(directions) > 3:
            raise ValueError("directions must contain at most 3 items")
        if not str(payload.get("user_choice", "")).strip():
            raise ValueError("user_choice is required")
        return
    if gate == "D":
        for field in ("decision_rationale", "applies_to", "excludes", "execution_approach"):
            if not str(payload.get(field, "")).strip():
                raise ValueError(f"{field} is required")
        return
    if gate == "X":
        dims = active_x_dimensions(constraints)
        if is_x_dimension_active(constraints, "acceptance_criteria"):
            if not str(payload.get("acceptance_criteria", "")).strip():
                raise ValueError("acceptance_criteria is required")
        if is_x_dimension_active(constraints, "implementation_sketch"):
            for field in ("key_changes", "critical_constraints", "reversibility"):
                if not str(payload.get(field, "")).strip():
                    raise ValueError(f"{field} is required")
        if not dims:
            raise ValueError("at least one X dimension must be active")
        return
    if gate == "R":
        exit_path = str(payload.get("exit", "")).strip()
        if exit_path not in {"loop_b", "dc", "rs"}:
            raise ValueError("exit must be loop_b, dc, or rs")
        if exit_path == "rs":
            reopen_gate = str(payload.get("reopen_gate", "")).strip()
            if reopen_gate not in LOOP_A:
                raise ValueError("reopen_gate must be one of Q, E, D, X for R exit rs")
        assumptions = payload.get("assumptions", [])
        if not isinstance(assumptions, list):
            raise ValueError("assumptions must be an array")
        for item in assumptions:
            if not isinstance(item, dict):
                raise ValueError("each assumption entry must be an object")
            if not str(item.get("id", "")).strip():
                raise ValueError("assumption id is required")
            risk = str(item.get("risk", "")).strip()
            if risk not in RISK_LEVELS:
                raise ValueError(f"invalid risk for {item.get('id')}: {risk!r}")
            if not str(item.get("consequence", "")).strip():
                raise ValueError(f"consequence is required for {item.get('id')}")
        return
    if gate == "V":
        exit_path = str(payload.get("exit", "")).strip()
        if exit_path not in {"rr", "dc"}:
            raise ValueError("exit must be rr or dc")
        assumptions = payload.get("assumptions", [])
        if not isinstance(assumptions, list):
            raise ValueError("assumptions must be an array")
        if exit_path == "dc" and not payload.get("batch_confirmed"):
            raise ValueError("batch_confirmed must be true for V exit dc")
        for item in assumptions:
            if not isinstance(item, dict):
                raise ValueError("each assumption entry must be an object")
            entry_id = str(item.get("id", "")).strip()
            if not entry_id:
                raise ValueError("assumption id is required")
            if not str(item.get("verification", "")).strip():
                raise ValueError(f"verification is required for {entry_id}")
        return
    if gate == "RR":
        exit_path = str(payload.get("exit", "")).strip()
        if exit_path not in {"dc", "return_r", "human_decision"}:
            raise ValueError("exit must be dc, return_r, or human_decision")
        assumptions = payload.get("assumptions", [])
        if not isinstance(assumptions, list):
            raise ValueError("assumptions must be an array")
        for item in assumptions:
            if not isinstance(item, dict):
                raise ValueError("each assumption entry must be an object")
            if not str(item.get("id", "")).strip():
                raise ValueError("assumption id is required")
            if "released" not in item:
                raise ValueError(f"released flag required for {item.get('id')}")
        return
    if gate == "DC":
        if not payload.get("user_confirmed"):
            raise ValueError("user_confirmed must be true for DC gate-close")
        return
    raise ValueError(f"unsupported gate-close payload validation for {gate!r}")


def _apply_r_register_updates(
    registers_path: Path,
    payload: dict[str, Any],
    *,
    exit_path: str,
) -> None:
    registers = load_registers(registers_path, r_gate_closed=False)
    by_id = {str(item.get("id")): item for item in payload.get("assumptions", []) if isinstance(item, dict)}
    for entry in registers.get("assumptions", []):
        if not isinstance(entry, dict):
            continue
        update = by_id.get(str(entry.get("id")))
        if update is None:
            continue
        entry["risk"] = str(update.get("risk")).strip()
        entry["consequence"] = str(update.get("consequence", "")).strip()
        if exit_path == "dc" and str(entry.get("state", "")) == "pending":
            entry["state"] = "verified"
    save_registers(registers_path, registers, r_gate_closed=True)
    return None


def _apply_r_prior_signoff(registers_path: Path) -> None:
    """Mark all pending prior entries verified at R (R签字确认)."""
    registers = load_registers(registers_path, r_gate_closed=True)
    for entry in registers.get("prior", []):
        if isinstance(entry, dict) and str(entry.get("state", "")) == "pending":
            entry["state"] = "verified"
    save_registers(registers_path, registers, r_gate_closed=True)


def _apply_v_register_updates(registers_path: Path, payload: dict[str, Any]) -> None:
    registers = load_registers(registers_path, r_gate_closed=True)
    by_id = {
        str(item.get("id")): item
        for item in payload.get("assumptions", [])
        if isinstance(item, dict)
    }
    for entry in registers.get("assumptions", []):
        if not isinstance(entry, dict):
            continue
        update = by_id.get(str(entry.get("id")))
        if update is None:
            continue
        entry["verification"] = str(update.get("verification", "")).strip()
        if "release_tracking" in update:
            entry["release_tracking"] = bool(update["release_tracking"])
        risk = str(update.get("risk", entry.get("risk", ""))).strip()
        if risk in RISK_LEVELS:
            entry["risk"] = risk
    save_registers(registers_path, registers, r_gate_closed=True)


def _apply_rr_register_updates(registers_path: Path, payload: dict[str, Any]) -> None:
    registers = load_registers(registers_path, r_gate_closed=True)
    by_id = {
        str(item.get("id")): item
        for item in payload.get("assumptions", [])
        if isinstance(item, dict)
    }
    for entry in registers.get("assumptions", []):
        if not isinstance(entry, dict):
            continue
        update = by_id.get(str(entry.get("id")))
        if update is None:
            continue
        if bool(update.get("released")):
            entry["state"] = "verified"
    save_registers(registers_path, registers, r_gate_closed=True)


def _rr_scope_entries(registers: dict[str, Any]) -> list[dict[str, Any]]:
    scoped: list[dict[str, Any]] = []
    for entry in registers.get("assumptions", []):
        if isinstance(entry, dict) and _needs_rr_scope(entry):
            scoped.append(entry)
    return scoped


def _validate_rr_exit_against_registers(
    registers: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    scoped = _rr_scope_entries(registers)
    by_id = {
        str(item.get("id")): item
        for item in payload.get("assumptions", [])
        if isinstance(item, dict)
    }
    scope_ids = {str(entry.get("id")) for entry in scoped}
    missing = scope_ids - set(by_id)
    if missing:
        raise ValueError(f"missing RR-scope assumptions in payload: {sorted(missing)}")

    exit_path = str(payload.get("exit", "")).strip()
    released_flags = [bool(by_id[entry_id].get("released")) for entry_id in scope_ids]
    all_released = bool(released_flags) and all(released_flags)
    any_unreleased = any(not flag for flag in released_flags)

    if exit_path == "human_decision" and not any_unreleased:
        raise ValueError("RR exit human_decision requires at least one unreleased item")
    if exit_path in {"dc", "return_r"} and not all_released:
        raise ValueError(f"RR exit {exit_path} requires all scope items released")

    if exit_path == "return_r":
        new_pending = [
            entry
            for entry in registers.get("assumptions", [])
            if isinstance(entry, dict)
            and str(entry.get("state", "")) == "pending"
            and str(entry.get("source", "")) in {"V", "RR"}
        ]
        if not new_pending:
            raise ValueError("RR exit return_r requires new pending assumptions from V/RR")


def _apply_gate_close_doc(
    doc_path: Path,
    gate: str,
    payload: dict[str, Any],
    *,
    constraints: dict[str, Any],
) -> None:
    doc = load_decision_doc(doc_path)
    if gate == "Q":
        body = render_problem_body(
            problem_statement=str(payload.get("problem_statement", "")),
            constraints=str(payload.get("constraints", "")),
        )
        doc = replace_section(doc, "problem", body, constraints=constraints)
    elif gate == "E":
        directions = payload.get("directions", [])
        excluded = payload.get("excluded", [])
        if not isinstance(excluded, list):
            excluded = []
        body = render_direction_body(
            directions=directions,
            excluded=excluded,
            user_choice=str(payload.get("user_choice", "")).strip(),
        )
        doc = replace_section(doc, "direction", body, constraints=constraints)
    elif gate == "D":
        doc = replace_section(
            doc,
            "decision_rationale",
            render_decision_rationale_body(rationale=str(payload.get("decision_rationale", ""))),
            constraints=constraints,
        )
        doc = replace_section(
            doc,
            "scope",
            render_scope_body(
                applies_to=str(payload.get("applies_to", "")),
                excludes=str(payload.get("excludes", "")),
                execution_approach=str(payload.get("execution_approach", "")),
            ),
            constraints=constraints,
        )
    elif gate == "X":
        impact = payload.get("impact_surface", [])
        deps = payload.get("external_dependencies", [])
        if not isinstance(impact, list):
            impact = []
        if not isinstance(deps, list):
            deps = []
        body = render_execution_analysis_body(
            acceptance_criteria=str(payload.get("acceptance_criteria", "")),
            gap=str(payload.get("gap", "None")),
            impact_surface=impact,
            external_dependencies=deps,
            key_changes=str(payload.get("key_changes", "")),
            critical_constraints=str(payload.get("critical_constraints", "")),
            reversibility=str(payload.get("reversibility", "")),
            x_dimensions=active_x_dimensions(constraints),
        )
        doc = replace_section(doc, "execution_analysis", body, constraints=constraints)
    elif gate == "R":
        pass
    else:
        raise ValueError(f"unsupported gate for doc patch: {gate}")
    save_decision_doc(doc_path, doc)


def cmd_gate_activate(project_root: Path, cycle_id: str, stage: str, gate: str) -> int:
    paths = _paths(project_root, cycle_id, stage)
    try:
        state = load_gate_state(paths["gate_state"])
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    prereq_error = _validate_gate_activate_prereqs(state, gate)
    if prereq_error:
        return _emit_error(prereq_error)

    updated = activate_gate(state, gate)
    save_gate_state(paths["gate_state"], updated)
    _emit({"ok": True, "gate": gate, "active_gate": updated["active_gate"]})
    return 0


def _collect_delivery_errors(
    state: dict[str, Any],
    registers: dict[str, Any],
    doc: str,
    *,
    constraints: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if state["active_gate"] != "DC":
        errors.append(f"active_gate must be DC, got {state['active_gate']!r}")

    for gate in ("Q", "E", "D", "X", "R"):
        if not is_gate_closed(state, gate):
            errors.append(f"gate {gate} is not closed")

    skipped = list(state.get("skipped_gates") or [])
    if "V" not in skipped and not is_gate_closed(state, "V"):
        errors.append("gate V is not closed")
    if "RR" not in skipped and not is_gate_closed(state, "RR"):
        errors.append("gate RR is not closed")

    errors.extend(check_decision_doc_ready(doc, constraints=constraints))

    for entry in registers.get("assumptions", []):
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id", ""))
        risk = str(entry.get("risk", "")).strip()
        verification = str(entry.get("verification") or "").strip()
        if risk == "H":
            if not verification:
                errors.append(f"{entry_id}: High-risk missing verification")
            else:
                try:
                    _validate_high_risk_verification(verification, entry_id=entry_id)
                except ValueError as exc:
                    errors.append(str(exc))
        elif risk in {"M", "L"} and not verification:
            errors.append(f"{entry_id}: missing verification")
        if str(entry.get("state", "")) == "pending" and risk:
            errors.append(f"{entry_id}: assumption still pending")
    return errors


def cmd_check_delivery_ready(project_root: Path, cycle_id: str, stage: str) -> int:
    paths = _paths(project_root, cycle_id, stage)
    try:
        state = load_gate_state(paths["gate_state"])
        r_closed = is_gate_closed(state, "R")
        registers = load_registers(paths["registers"], r_gate_closed=r_closed)
        doc = load_decision_doc(paths["decision_doc"])
        constraints = _load_session_constraints(project_root, cycle_id, stage)
        errors = _collect_delivery_errors(state, registers, doc, constraints=constraints)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, "ready": not errors, "errors": errors})
    return 0


def cmd_deliver(project_root: Path, cycle_id: str, stage: str) -> int:
    paths = _paths(project_root, cycle_id, stage)
    try:
        state = load_gate_state(paths["gate_state"])
        if not is_gate_closed(state, "DC"):
            return _emit_error("DC gate must be closed before deliver")
        r_closed = is_gate_closed(state, "R")
        registers = load_registers(paths["registers"], r_gate_closed=r_closed)
        doc = load_decision_doc(paths["decision_doc"])
        constraints = _load_session_constraints(project_root, cycle_id, stage)
        errors = _collect_delivery_errors(state, registers, doc, constraints=constraints)
        if errors:
            return _emit_error("; ".join(errors))
        ss_path = project_root / session_state_path(cycle_id, stage)
        write_session_state(ss_path, "Delivered")
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit(
        {
            "ok": True,
            "session_state": "Delivered",
            "session_state_path": ss_path.as_posix(),
        }
    )
    return 0


def cmd_gate_close(
    project_root: Path,
    cycle_id: str,
    stage: str,
    gate: str,
    payload: dict[str, Any],
) -> int:
    paths = _paths(project_root, cycle_id, stage)
    try:
        state = load_gate_state(paths["gate_state"])
        constraints = _load_session_constraints(project_root, cycle_id, stage)
        prereq_error = _validate_gate_close_prereqs(state, gate)
        if prereq_error:
            return _emit_error(prereq_error)
        _validate_gate_close_payload(gate, payload, constraints=constraints)
        if gate == "R":
            exit_path = str(payload.get("exit", "")).strip()
            if exit_path != "rs":
                if payload.get("assumptions"):
                    _apply_r_register_updates(paths["registers"], payload, exit_path=exit_path)
                else:
                    save_registers(
                        paths["registers"],
                        load_registers(paths["registers"], r_gate_closed=False),
                        r_gate_closed=True,
                    )
                _apply_r_prior_signoff(paths["registers"])
                sync_registers_to_doc(
                    paths["decision_doc"],
                    paths["registers"],
                    r_gate_closed=True,
                    constraints=constraints,
                )
                updated = close_gate_r(state, exit_path=exit_path)
            else:
                if payload.get("assumptions"):
                    _apply_r_register_updates(paths["registers"], payload, exit_path=exit_path)
                    sync_registers_to_doc(
                        paths["decision_doc"],
                        paths["registers"],
                        r_gate_closed=True,
                        constraints=constraints,
                    )
                updated = state
        elif gate == "V":
            exit_path = str(payload.get("exit", "")).strip()
            registers = load_registers(paths["registers"], r_gate_closed=True)
            _validate_v_exit_against_registers(registers, payload)
            _apply_v_register_updates(paths["registers"], payload)
            sync_registers_to_doc(
                paths["decision_doc"],
                paths["registers"],
                r_gate_closed=True,
                constraints=constraints,
            )
            updated = close_gate_v(state, exit_path=exit_path)
        elif gate == "RR":
            exit_path = str(payload.get("exit", "")).strip()
            registers = load_registers(paths["registers"], r_gate_closed=True)
            _validate_rr_exit_against_registers(registers, payload)
            if exit_path == "human_decision":
                _apply_rr_register_updates(paths["registers"], payload)
                sync_registers_to_doc(
                    paths["decision_doc"],
                    paths["registers"],
                    r_gate_closed=True,
                    constraints=constraints,
                )
                updated = state
            else:
                _apply_rr_register_updates(paths["registers"], payload)
                sync_registers_to_doc(
                    paths["decision_doc"],
                    paths["registers"],
                    r_gate_closed=True,
                    constraints=constraints,
                )
                updated = close_gate_rr(state, exit_path=exit_path)
        elif gate == "DC":
            registers = load_registers(paths["registers"], r_gate_closed=True)
            doc = load_decision_doc(paths["decision_doc"])
            errors = _collect_delivery_errors(state, registers, doc, constraints=constraints)
            if errors:
                return _emit_error("; ".join(errors))
            updated = close_gate(state, gate)
        else:
            updated = close_gate(state, gate)
            _apply_gate_close_doc(paths["decision_doc"], gate, payload, constraints=constraints)
        save_gate_state(paths["gate_state"], updated)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    result: dict[str, Any] = {
        "ok": True,
        "gate": gate,
        "status": "active"
        if (gate == "RR" and payload.get("exit") == "human_decision")
        or (gate == "R" and payload.get("exit") == "rs")
        else "closed",
        "active_gate": updated["active_gate"],
    }
    if gate in {"R", "V", "RR"}:
        result["exit"] = payload.get("exit")
    if gate == "R" and payload.get("exit") == "rs":
        result["reopen_gate"] = payload.get("reopen_gate")
    if gate in {"R", "V"} and payload.get("exit") != "rs":
        result["skipped_gates"] = updated.get("skipped_gates", [])
    _emit(result)
    return 0


def cmd_invalidate_from(project_root: Path, cycle_id: str, stage: str, gate: str) -> int:
    paths = _paths(project_root, cycle_id, stage)
    try:
        state = load_gate_state(paths["gate_state"])
        if gate not in GATE_ORDER:
            return _emit_error(f"invalid gate: {gate!r}")
        if gate not in LOOP_A and gate != "R":
            return _emit_error(f"invalidate-from supports LoopA gates and R, got {gate!r}")
        updated = invalidate_from_gate(state, gate)
        save_gate_state(paths["gate_state"], updated)
        doc = load_decision_doc(paths["decision_doc"])
        doc = clear_sections_downstream(doc, gate)
        save_decision_doc(paths["decision_doc"], doc)
        r_closed = is_gate_closed(updated, "R")
        constraints = _load_session_constraints(project_root, cycle_id, stage)
        sync_registers_to_doc(
            paths["decision_doc"],
            paths["registers"],
            r_gate_closed=r_closed,
            constraints=constraints,
        )
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, "gate": gate, "active_gate": updated["active_gate"]})
    return 0


def cmd_migrate_session(project_root: Path, cycle_id: str, stage: str) -> int:
    paths = _paths(project_root, cycle_id, stage)
    try:
        if not needs_migration(paths["session_dir"]):
            return _emit_error("session does not require migration (gate-state exists or no session-state)")
        result = migrate_session_dir(
            paths["session_dir"],
            project_root=project_root,
            cycle_id=cycle_id,
            stage=stage,
        )
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, **result})
    return 0


def _load_payload(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")
    return data


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnostic gate state control.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID.")
    parser.add_argument("--stage", default="diagnostic", help="Diagnostic stage name.")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init-session", help="Bootstrap session artifacts.")
    init_parser.add_argument(
        "--domain-constraints",
        default="",
        help="Optional JSON override for domain-constraints (omitted_sections, x_dimensions).",
    )

    sub.add_parser("resolve-context", help="Return session context JSON.")

    activate = sub.add_parser("gate-activate", help="Activate a gate.")
    activate.add_argument("--gate", required=True)

    close = sub.add_parser("gate-close", help="Close the active gate.")
    close.add_argument("--gate", required=True)
    close.add_argument("--payload", required=True, help="JSON payload string.")

    invalidate = sub.add_parser("invalidate-from", help="Invalidate gate and downstream.")
    invalidate.add_argument("--gate", required=True)

    sub.add_parser("check-delivery-ready", help="Validate readiness for DC delivery.")
    sub.add_parser("deliver", help="Set session-state Delivered after DC closed.")
    sub.add_parser("migrate-session", help="Migrate legacy session to gate-state architecture.")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    stage = args.stage.strip()

    if args.command == "init-session":
        domain_override = None
        raw = getattr(args, "domain_constraints", "").strip()
        if raw:
            try:
                domain_override = _load_payload(raw)
            except (json.JSONDecodeError, ValueError) as exc:
                return _emit_error(str(exc))
        return cmd_init_session(
            project_root,
            cycle_id,
            stage,
            domain_override=domain_override,
        )
    if args.command == "resolve-context":
        return cmd_resolve_context(project_root, cycle_id, stage)
    if args.command == "gate-activate":
        return cmd_gate_activate(project_root, cycle_id, stage, args.gate.strip())
    if args.command == "gate-close":
        try:
            payload = _load_payload(args.payload)
        except (json.JSONDecodeError, ValueError) as exc:
            return _emit_error(str(exc))
        return cmd_gate_close(project_root, cycle_id, stage, args.gate.strip(), payload)
    if args.command == "invalidate-from":
        return cmd_invalidate_from(project_root, cycle_id, stage, args.gate.strip())
    if args.command == "check-delivery-ready":
        return cmd_check_delivery_ready(project_root, cycle_id, stage)
    if args.command == "deliver":
        return cmd_deliver(project_root, cycle_id, stage)
    if args.command == "migrate-session":
        return cmd_migrate_session(project_root, cycle_id, stage)
    return _emit_error(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
