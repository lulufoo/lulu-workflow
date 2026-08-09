#!/usr/bin/env python3
"""Gate state machine control for decision sessions.

Subcommands:
    init-session           Bootstrap gate-state, registers (no decision-doc at init)
    resolve-context        JSON session context for runners (gates, registers, constraints)
    get-payload            Read persisted gate-payloads (by gate list or --stale-only)
    gate-activate          Activate a gate (e.g. re-activate Q after RS)
    gate-close             Close active gate, write gate-payload, advance pointer
    batch-reclose          Atomically re-close consecutive stale align gates (Q/GL/E/D/X)
    stale-from             Realign: mark gate + reached downstream stale (no payload delete)
    rs-commit              Prevalidated Realign: stale + register batch + context
                           (if session Frozen: mark stale then unfreeze — P1.5 A′)
    reopen                 Leave Completed/InProgress → Frozen ($DEC_REOPEN; P1.3 A)
    check-delivery-ready   Structural audit + gates/registers for DC completion
    prepare                Verify delivery-ready + decision-doc without changing
                           session state or delivered refs.
    complete               Set session-state Completed (requires DC closed +
                           decision-doc). Nested approach main/Dx skips cycle
                           delivered-refs (holder stage deliver owns them).
                           Alias: deliver.
    complete-assumption    Write release_terms + risk_state=completed (R active or closed)
    set-risk-state         Set risk_state to ignore|open on a risk row (R active or closed)
    apply-r-assumptions    Persist R expose draft risk fields without closing R
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


from dec_decision_doc_schema import GATE_CLOSE_PREREQ  # noqa: E402
from dec_after_dc import build_after_dc  # noqa: E402
from dec_domain_constraints_schema import (  # noqa: E402
    ALL_X_DIMENSIONS,
    KERNEL_STAGE,
    active_x_dimensions,
    default_kernel_constraints,
    is_x_dimension_active,
    load_constraints_config,
    load_domain_constraints,
    merge_domain_constraints,
    save_domain_constraints,
)
from dec_gate_payload_schema import (  # noqa: E402
    gate_payload_path,
    load_gate_payload,
    save_gate_payload,
)
from dec_gate_state_schema import (  # noqa: E402
    GATE_ORDER,
    LEGACY_RR_ACTIVE_ERROR,
    RS_REALIGN_GATES,
    activate_gate,
    close_gate,
    close_gate_r,
    init_gate_state,
    is_gate_closed,
    is_gate_reached,
    load_gate_state,
    mark_stale_from_gate,
    save_gate_state,
)
from dec_register_schema import (  # noqa: E402
    RISK_CLASSES,
    RISK_LEVELS,
    RISK_STATES,
    init_registers,
    load_registers,
    save_registers,
    validate_release_terms,
)
from dec_session_render import render_reply_header  # noqa: E402
from dec_session_paths import (  # noqa: E402
    resolve_session_root_for_command,
    session_artifact_paths,
    skips_cycle_delivered_ref_on_deliver,
    stage_outer_root,
)
from dec_session_state_schema import (  # noqa: E402
    read_current_state,
    session_state_file,
    set_session_frozen,
    unfreeze_session,
    write_session_state,
)
from dec_workflow_common import (  # noqa: E402
    CACHE_DIR,
    detect_cycle_type,
    session_base_dir,
)

from dec_migrate_session import migrate_session_dir, needs_migration  # noqa: E402
from dec_register_control import (  # noqa: E402
    prepare_register_batch_operations,
)

_STALE_R_REVIEW_STATES = {
    "keep_completed": "completed",
    "reverified": "completed",
    "ignore": "ignore",
    "non_risk": "none",
}


def _reject_if_legacy_rr_active(state: dict[str, Any]) -> str | None:
    if str(state.get("active_gate", "")) == "RR":
        return LEGACY_RR_ACTIVE_ERROR
    return None


def _r_risk_fields_allowed(gate_state: dict[str, Any]) -> bool:
    return is_gate_reached(gate_state, "R")


def _register_io_flags(gate_state: dict[str, Any]) -> dict[str, bool]:
    r_closed = is_gate_closed(gate_state, "R")
    allowed = _r_risk_fields_allowed(gate_state)
    return {
        "r_gate_closed": r_closed,
        "r_risk_fields_allowed": allowed,
    }


def _find_assumption(registers: dict[str, Any], entry_id: str) -> dict[str, Any] | None:
    for entry in registers.get("assumptions", []):
        if isinstance(entry, dict) and str(entry.get("id")) == entry_id:
            return entry
    return None


def _is_risk_row(entry: dict[str, Any]) -> bool:
    level = str(entry.get("risk_level", "")).strip()
    klass = str(entry.get("risk_class", "")).strip()
    state = str(entry.get("risk_state", "")).strip()
    return not (level == "none" and klass == "none" and state == "none")


def _reject_if_r_assumption_gate_closed(state: dict[str, Any]) -> str | None:
    active = str(state.get("active_gate", ""))
    if active == "R" or is_gate_closed(state, "R"):
        return None
    return "complete-assumption and set-risk-state require R active or closed"


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _emit_error(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    return 1


def _parse_constraints_path(raw: str) -> Path | None:
    text = raw.strip()
    if not text:
        return None
    return Path(text).expanduser().resolve()


def _load_constraints_for_init(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None,
) -> dict[str, Any]:
    if constraints_path is not None:
        return load_constraints_config(constraints_path, stage=stage)
    if stage == KERNEL_STAGE:
        return default_kernel_constraints(stage=stage)
    raise ValueError(f"--constraints is required for stage {stage!r}")


def _paths(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> dict[str, Path]:
    root = resolve_session_root_for_command(
        project_root,
        cycle_id,
        stage,
        CACHE_DIR,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    return session_artifact_paths(root)


def _reject_if_frozen(paths: dict[str, Path]) -> int | None:
    """Hard-reject ordinary gate advance while session is Frozen (P1.3a / P1.4′)."""
    ss = paths.get("session_state") or session_state_file(paths["session_dir"])
    if not ss.exists():
        return None
    try:
        if read_current_state(ss) == "Frozen":
            return _emit_error(
                "session is Frozen; complete RS then $RS_COMMIT to stale and unfreeze"
            )
    except ValueError as exc:
        return _emit_error(str(exc))
    return None


def _load_session_constraints(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
    paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    resolved = paths or _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    path = resolved["domain_constraints"]
    if path.exists():
        return load_domain_constraints(path)
    return _load_constraints_for_init(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
    )


def _validate_gate_activate_prereqs(state: dict[str, Any], gate: str) -> str | None:
    if gate == "O":
        return "cannot activate O; it is the initial gate"
    if gate == "Q":
        if not is_gate_closed(state, "O"):
            return "gate O must be closed before activating Q"
        return None
    if gate == "GL":
        if not is_gate_closed(state, "Q"):
            return "gate Q must be closed before activating GL"
        return None
    if gate == "E":
        if not is_gate_closed(state, "GL"):
            return "gate GL must be closed before activating E"
        return None
    prev = {"D": "E", "X": "D", "R": "X", "DC": "R"}.get(gate)
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
    constraints_path: Path | None = None,
    domain_override: dict[str, Any] | None = None,
    session_dir: Path | None = None,
    commit_active: bool = True,
) -> int:
    try:
        constraints = _load_constraints_for_init(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
        )
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir
        if session_dir is not None
        else project_root
        / session_base_dir(
            cycle_id,
            stage,
            project_root=project_root,
            constraints_path=constraints_path,
        ),
    )
    paths["session_dir"].mkdir(parents=True, exist_ok=True)
    if paths["gate_state"].exists():
        return _emit_error("gate-state already exists; use a new cycle or remove session dir")
    if domain_override:
        constraints = merge_domain_constraints(constraints, domain_override)
    save_domain_constraints(paths["domain_constraints"], constraints)

    gate_state = init_gate_state(cycle_id=cycle_id, stage=stage)
    save_gate_state(paths["gate_state"], gate_state)

    registers = init_registers(cycle_id=cycle_id, stage=stage)
    save_registers(paths["registers"], registers, r_gate_closed=False)

    if commit_active:
        try:
            from dec_active_control import _commit_active  # noqa: WPS433

            _commit_active(
                project_root,
                cycle_id,
                stage,
                session_dir=paths["session_dir"],
                constraints_path=constraints_path,
            )
        except (FileNotFoundError, ValueError) as exc:
            return _emit_error(f"failed to set Active Session: {exc}")

    from dec_domain_constraints_schema import context_docs_map  # noqa: WPS433

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
            "context_docs": context_docs_map(constraints),
            "message": "诊断会话已启动。工作流已就绪，可以开始 DDF 节点执行。",
        }
    )
    return 0


def build_resolve_context_payload(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    paths: dict[str, Path] | None = None,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
    gate_state_override: dict[str, Any] | None = None,
    registers_override: dict[str, Any] | None = None,
    session_state_override: str | None = None,
) -> dict[str, Any]:
    """Session context dict for resolve-context / register-commit stdout."""
    resolved_paths = paths or _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    gate_state = (
        gate_state_override
        if gate_state_override is not None
        else load_gate_state(resolved_paths["gate_state"])
    )
    rr_err = _reject_if_legacy_rr_active(gate_state)
    if rr_err:
        raise ValueError(rr_err)
    reg_flags = _register_io_flags(gate_state)
    registers = (
        registers_override
        if registers_override is not None
        else load_registers(resolved_paths["registers"], **reg_flags)
    )
    constraints = _load_session_constraints(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        paths=resolved_paths,
    )
    cycle_type = detect_cycle_type(cycle_id)
    gl_payload: dict[str, Any] | None = None
    if is_gate_closed(gate_state, "GL"):
        payloads_dir = resolved_paths.get("payloads_dir")
        if payloads_dir is None:
            payloads_dir = resolved_paths["session_dir"] / "gate-payloads"
        gl_path = gate_payload_path(payloads_dir, "GL")
        if gl_path.exists():
            gl_payload = load_gate_payload(gl_path)
    session_state = session_state_override
    if session_state is None:
        ss_path = resolved_paths.get("session_state") or session_state_file(
            resolved_paths["session_dir"]
        )
        if ss_path.exists():
            try:
                session_state = read_current_state(ss_path)
            except ValueError:
                session_state = None
    return {
        "cycle_id": cycle_id,
        "stage": stage,
        "cycle_type": cycle_type,
        "session_dir": resolved_paths["session_dir"].as_posix(),
        "session_state": session_state,
        "gate_state_path": resolved_paths["gate_state"].as_posix(),
        "registers_path": resolved_paths["registers"].as_posix(),
        "decision_doc_path": resolved_paths["decision_doc"].as_posix(),
        "domain_constraints_path": resolved_paths["domain_constraints"].as_posix(),
        "active_gate": gate_state["active_gate"],
        "gates": gate_state["gates"],
        "skipped_gates": gate_state.get("skipped_gates", []),
        "domain_constraints": constraints,
        "registers": registers,
        "gl": gl_payload,
        "reply_header": render_reply_header(gate_state, registers),
        # decision never resolves context itself — this is a pure read of
        # whatever the holder's own resolver script handed to $DEC_START at init
        # time via --domain-constraints-file (frozen into the session's own copy).
        "context": constraints.get("context") or {"docs": {}},
        "after_dc": build_after_dc(stage, cycle_type),
    }


def cmd_resolve_context(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    try:
        payload = build_resolve_context_payload(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
            session_dir=session_dir,
        )
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, **payload})
    return 0


_IMPLEMENTED_GATES = frozenset({"O", "Q", "GL", "E", "D", "X", "R", "DC"})
def _validate_gl_close_payload(
    payload: dict[str, Any], *, constraints: dict[str, Any]
) -> None:
    """Mechanical close predicates for spine gate GL (intent probe)."""
    required = active_x_dimensions(constraints)
    exchanges = payload.get("exchanges")
    if not isinstance(exchanges, list) or len(exchanges) < 1:
        raise ValueError("exchanges must be a non-empty array")
    seen: set[str] = set()
    for index, row in enumerate(exchanges):
        if not isinstance(row, dict):
            raise ValueError(f"exchanges[{index}] must be an object")
        lens = str(row.get("lens", "")).strip()
        if lens not in ALL_X_DIMENSIONS:
            raise ValueError(
                f"exchanges[{index}].lens must be one of {list(ALL_X_DIMENSIONS)}, "
                f"got {lens!r}"
            )
        if lens not in required:
            raise ValueError(
                f"exchanges[{index}].lens {lens!r} is not in active x_dimensions "
                f"{sorted(required)}"
            )
        seen.add(lens)
        na = row.get("na") is True
        question = str(row.get("question", "")).strip()
        answer = str(row.get("answer", "")).strip()
        if na:
            if not answer:
                raise ValueError(
                    f"exchanges[{index}].answer must be non-empty when na is true"
                )
        else:
            if not question:
                raise ValueError(
                    f"exchanges[{index}].question is required when na is not true"
                )
            if not answer:
                raise ValueError(
                    f"exchanges[{index}].answer is required when na is not true"
                )
    missing = sorted(required - seen)
    if missing:
        raise ValueError(
            f"exchanges must cover active x_dimensions {sorted(required)}; "
            f"missing {missing}"
        )
    if payload.get("user_confirmed") is not True:
        raise ValueError("user_confirmed must be true for GL gate-close")

_H_VERIFICATION_PARTS = ("Method:", "Owner:", "Timing:", "Release condition:")


def _risk_class_of(entry: dict[str, Any]) -> str:
    return str(entry.get("risk_class", "")).strip()


def _risk_level_of(entry: dict[str, Any]) -> str:
    return str(entry.get("risk_level", entry.get("risk", ""))).strip()


def _risk_state_of(entry: dict[str, Any]) -> str:
    return str(entry.get("risk_state", entry.get("disposition", ""))).strip()


def _validate_r_assumption_payload(item: dict[str, Any], *, exit_path: str) -> None:
    entry_id = str(item.get("id", "")).strip()
    if not entry_id:
        raise ValueError("assumption id is required")
    risk_level = str(item.get("risk_level", item.get("risk", ""))).strip()
    if risk_level not in RISK_LEVELS:
        raise ValueError(f"invalid risk_level for {entry_id}: {risk_level!r}")
    if not str(item.get("risk_consequence", item.get("consequence", ""))).strip():
        raise ValueError(f"risk_consequence is required for {entry_id}")
    risk_class = str(item.get("risk_class", "")).strip()
    if risk_class not in RISK_CLASSES:
        raise ValueError(f"invalid risk_class for {entry_id}: {risk_class!r}")
    risk_state = str(item.get("risk_state", "")).strip()
    if risk_state and risk_state not in RISK_STATES:
        raise ValueError(f"invalid risk_state for {entry_id}: {risk_state!r}")
    if risk_state == "completed":
        raise ValueError(
            f"{entry_id}: completed only via complete-assumption "
            "(not gate-close or apply-r-assumptions)"
        )
    if exit_path == "dc" and risk_state == "open":
        raise ValueError(
            f"R exit dc forbids risk_state=open on {entry_id}; "
            "complete-assumption or set-risk-state first"
        )


def _validate_open_risk_states_for_dc(registers: dict[str, Any]) -> None:
    open_ids = [
        str(entry.get("id"))
        for entry in registers.get("assumptions", [])
        if isinstance(entry, dict)
        and _is_risk_row(entry)
        and _risk_state_of(entry) == "open"
    ]
    if open_ids:
        raise ValueError(
            "R exit dc forbids risk_state=open: "
            f"{sorted(open_ids)}; use complete-assumption or set-risk-state"
        )


def _validate_stale_r_review(
    payload: dict[str, Any],
    registers: dict[str, Any],
) -> None:
    if payload.get("assumptions"):
        raise ValueError(
            "stale R exit dc requires persisted risk rows; "
            "apply changes before gate-close and pass assumptions=[]"
        )
    review = payload.get("stale_review")
    if not isinstance(review, dict):
        raise ValueError("stale_review is required for stale R exit dc")
    if review.get("user_confirmed") is not True:
        raise ValueError("stale_review.user_confirmed must be true")
    affected_ids = review.get("affected_ids")
    if not isinstance(affected_ids, list) or any(
        not isinstance(entry_id, str) or not entry_id.strip()
        for entry_id in affected_ids
    ):
        raise ValueError("stale_review.affected_ids must be an array of ids")
    normalized_ids = [entry_id.strip() for entry_id in affected_ids]
    if len(set(normalized_ids)) != len(normalized_ids):
        raise ValueError("stale_review.affected_ids must be unique")
    dispositions = review.get("dispositions")
    if not isinstance(dispositions, dict):
        raise ValueError("stale_review.dispositions must be an object")
    if set(dispositions) != set(normalized_ids):
        raise ValueError(
            "stale_review.dispositions keys must match affected_ids exactly"
        )

    by_id = {
        str(entry.get("id")): entry
        for entry in registers.get("assumptions", [])
        if isinstance(entry, dict)
    }
    for entry_id in normalized_ids:
        entry = by_id.get(entry_id)
        if entry is None:
            raise ValueError(f"stale_review entry not found: {entry_id}")
        disposition = str(dispositions.get(entry_id, "")).strip()
        expected_state = _STALE_R_REVIEW_STATES.get(disposition)
        if expected_state is None:
            raise ValueError(
                f"invalid stale_review disposition for {entry_id}: {disposition!r}"
            )
        actual_state = _risk_state_of(entry)
        if actual_state != expected_state:
            raise ValueError(
                f"{entry_id}: stale_review disposition {disposition!r} "
                f"requires risk_state={expected_state!r}, got {actual_state!r}"
            )


def _validate_gate_close_prereqs(state: dict[str, Any], gate: str) -> str | None:
    if state["active_gate"] != gate:
        return f"active_gate is {state['active_gate']!r}, expected {gate!r}"
    entry = state["gates"].get(gate, {})
    status = str(entry.get("status", "")).lower()
    if status not in {"active", "stale"}:
        return f"gate {gate} is not active or stale (got {status!r})"

    prior = _required_prior_gate(gate)
    if prior and not is_gate_closed(state, prior):
        return f"gate {prior} must be closed before closing {gate}"
    if gate not in _IMPLEMENTED_GATES:
        return f"gate-close not implemented for gate {gate!r}"
    return None


def _validate_gate_close_payload(gate: str, payload: dict[str, Any], *, constraints: dict[str, Any]) -> None:
    if gate == "O":
        if not payload.get("user_confirmed"):
            raise ValueError("user_confirmed must be true for O gate-close")
        return
    if gate == "Q":
        if not str(payload.get("problem_statement", "")).strip():
            raise ValueError("problem_statement is required")
        return
    if gate == "GL":
        _validate_gl_close_payload(payload, constraints=constraints)
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
        if exit_path not in {"dc", "rs", "human_decision"}:
            raise ValueError("exit must be dc, rs, or human_decision")
        if exit_path == "rs":
            realign_gate = str(
                payload.get("realign_gate", payload.get("reopen_gate", ""))
            ).strip()
            if realign_gate not in RS_REALIGN_GATES:
                raise ValueError(
                    "realign_gate must be one of Q, GL, E, D, X for R exit rs"
                )
            payload["realign_gate"] = realign_gate
        assumptions = payload.get("assumptions", [])
        if not isinstance(assumptions, list):
            raise ValueError("assumptions must be an array")
        for item in assumptions:
            if not isinstance(item, dict):
                raise ValueError("each assumption entry must be an object")
            _validate_r_assumption_payload(item, exit_path=exit_path)
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
    gate_state: dict[str, Any],
) -> None:
    reg_flags = _register_io_flags(gate_state)
    reg_flags["r_risk_fields_allowed"] = True
    registers = load_registers(registers_path, **reg_flags)
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
        prior_risk_state = _risk_state_of(entry)
        risk_level = str(update.get("risk_level", update.get("risk", ""))).strip()
        entry["risk_level"] = risk_level
        entry["risk_consequence"] = str(
            update.get("risk_consequence", update.get("consequence", ""))
        ).strip()
        entry["risk_class"] = str(update.get("risk_class", "")).strip()
        if "risk_state" in update:
            entry["risk_state"] = str(update.get("risk_state", "")).strip()
        elif not entry.get("risk_state"):
            # D3 defaults when payload omits risk_state: H/M→open, L→ignore
            if risk_level == "L":
                entry["risk_state"] = "ignore"
            elif risk_level in {"H", "M"}:
                entry["risk_state"] = "open"
        if prior_risk_state == "completed" and _risk_state_of(entry) == "open":
            entry.pop("release_terms", None)
        for retired in ("risk", "consequence", "state", "verification", "disposition"):
            entry.pop(retired, None)
    save_flags = dict(reg_flags)
    save_flags["r_gate_closed"] = is_gate_closed(gate_state, "R") or bool(by_id)
    save_registers(registers_path, registers, **save_flags)


def _apply_r_prior_signoff(registers_path: Path, *, gate_state: dict[str, Any]) -> None:
    """Mark all pending prior entries verified at R (R签字确认)."""
    reg_flags = _register_io_flags(gate_state)
    registers = load_registers(registers_path, **reg_flags)
    for entry in registers.get("prior", []):
        if isinstance(entry, dict) and str(entry.get("state", "")) == "pending":
            entry["state"] = "verified"
    save_registers(registers_path, registers, **reg_flags)


def cmd_complete_assumption(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    entry_id: str,
    release_terms: str,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    try:
        state = load_gate_state(paths["gate_state"])
        rr_err = _reject_if_legacy_rr_active(state)
        if rr_err:
            return _emit_error(rr_err)
        gate_err = _reject_if_r_assumption_gate_closed(state)
        if gate_err:
            return _emit_error(gate_err)
        reg_flags = _register_io_flags(state)
        registers = load_registers(paths["registers"], **reg_flags)
        target = _find_assumption(registers, entry_id.strip())
        if target is None:
            return _emit_error(f"entry not found: {entry_id}")
        if not _is_risk_row(target):
            return _emit_error(f"{entry_id}: not a risk row (none triad)")
        if _risk_state_of(target) != "open":
            return _emit_error(
                f"{entry_id}: risk_state must be open (got {_risk_state_of(target)!r})"
            )
        validate_release_terms(release_terms, entry_id=entry_id)
        target["release_terms"] = release_terms.strip()
        target["risk_state"] = "completed"
        save_registers(paths["registers"], registers, **reg_flags)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))
    _emit({"ok": True, "entry": target})
    return 0


def cmd_set_risk_state(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    entry_id: str,
    risk_state: str,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    new_state = risk_state.strip()
    if new_state not in {"ignore", "open"}:
        return _emit_error("risk_state must be ignore or open (use complete-assumption for completed)")
    try:
        state = load_gate_state(paths["gate_state"])
        rr_err = _reject_if_legacy_rr_active(state)
        if rr_err:
            return _emit_error(rr_err)
        gate_err = _reject_if_r_assumption_gate_closed(state)
        if gate_err:
            return _emit_error(gate_err)
        reg_flags = _register_io_flags(state)
        registers = load_registers(paths["registers"], **reg_flags)
        target = _find_assumption(registers, entry_id.strip())
        if target is None:
            return _emit_error(f"entry not found: {entry_id}")
        if not _is_risk_row(target):
            return _emit_error(f"{entry_id}: not a risk row (none triad)")
        if _risk_state_of(target) == "completed" and new_state == "open":
            target.pop("release_terms", None)
        target["risk_state"] = new_state
        save_registers(paths["registers"], registers, **reg_flags)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))
    _emit({"ok": True, "entry": target})
    return 0


def cmd_apply_r_assumptions(
    project_root: Path,
    cycle_id: str,
    stage: str,
    payload: dict[str, Any],
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    """Persist R expose draft (risk fields) without closing the gate."""
    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    try:
        state = load_gate_state(paths["gate_state"])
        rr_err = _reject_if_legacy_rr_active(state)
        if rr_err:
            return _emit_error(rr_err)
        if str(state.get("active_gate", "")) != "R":
            return _emit_error("apply-r-assumptions requires active_gate=R")
        assumptions = payload.get("assumptions")
        if not isinstance(assumptions, list) or not assumptions:
            return _emit_error("assumptions array is required")
        for item in assumptions:
            if not isinstance(item, dict):
                return _emit_error("each assumption entry must be an object")
            _validate_r_assumption_payload(item, exit_path="human_decision")
        _apply_r_register_updates(paths["registers"], payload, gate_state=state)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))
    _emit({"ok": True, "applied": len(assumptions)})
    return 0


def _persist_gate_payload(
    paths: dict[str, Path],
    gate: str,
    payload: dict[str, Any],
) -> None:
    save_gate_payload(gate_payload_path(paths["payloads_dir"], gate), payload)


def _gate_close_persists_payload(gate: str, payload: dict[str, Any]) -> bool:
    if gate == "R" and str(payload.get("exit", "")).strip() in {"rs", "human_decision"}:
        return False
    return True


def cmd_gate_activate(
    project_root: Path,
    cycle_id: str,
    stage: str,
    gate: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    frozen = _reject_if_frozen(paths)
    if frozen is not None:
        return frozen
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
    project_root: Path,
    cycle_id: str,
    stage: str,
    state: dict[str, Any],
    registers: dict[str, Any],
    paths: dict[str, Path],
    *,
    constraints_path: Path | None = None,
    require_decision_doc: bool = False,
) -> list[str]:
    from dec_session_integrity import run_structural_audit  # noqa: WPS433

    errors: list[str] = []
    if state["active_gate"] != "DC":
        errors.append(f"active_gate must be DC, got {state['active_gate']!r}")

    for gate in ("O", "Q", "GL", "E", "D", "X", "R"):
        if not is_gate_closed(state, gate):
            errors.append(f"gate {gate} is not closed")

    errors.extend(
        run_structural_audit(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
        )
    )

    if require_decision_doc and not paths["decision_doc"].exists():
        errors.append("decision-doc not found; run session-integrity render before deliver")

    for entry in registers.get("assumptions", []):
        if not isinstance(entry, dict):
            continue
        if not _is_risk_row(entry):
            continue
        entry_id = str(entry.get("id", ""))
        risk_state = _risk_state_of(entry)
        if risk_state == "open":
            errors.append(f"{entry_id}: risk_state still open")
        if risk_state == "completed":
            terms = str(entry.get("release_terms") or "").strip()
            if not terms:
                errors.append(f"{entry_id}: completed missing release_terms")
            else:
                try:
                    validate_release_terms(terms, entry_id=entry_id)
                except ValueError as exc:
                    errors.append(str(exc))
    return errors


def cmd_check_delivery_ready(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    try:
        state = load_gate_state(paths["gate_state"])
        reg_flags = _register_io_flags(state)
        reg_flags["r_gate_closed"] = True
        registers = load_registers(paths["registers"], **reg_flags)
        errors = _collect_delivery_errors(
            project_root,
            cycle_id,
            stage,
            state,
            registers,
            paths,
            constraints_path=constraints_path,
            require_decision_doc=False,
        )
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, "ready": not errors, "errors": errors})
    return 0


def cmd_complete(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    """Mark the decision session Completed (node/session terminal, not stage Deliver)."""
    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    frozen = _reject_if_frozen(paths)
    if frozen is not None:
        return frozen
    try:
        state = load_gate_state(paths["gate_state"])
        if not is_gate_closed(state, "DC"):
            return _emit_error("DC gate must be closed before complete")
        reg_flags = _register_io_flags(state)
        reg_flags["r_gate_closed"] = True
        registers = load_registers(paths["registers"], **reg_flags)
        errors = _collect_delivery_errors(
            project_root,
            cycle_id,
            stage,
            state,
            registers,
            paths,
            constraints_path=constraints_path,
            require_decision_doc=True,
        )
        if errors:
            return _emit_error("; ".join(errors))
        ss_path = paths.get("session_state") or session_state_file(paths["session_dir"])
        doc_path = paths["decision_doc"]
        # Nested approach main/Dx: local Completed only; cycle refs via holder stage deliver.
        if not skips_cycle_delivered_ref_on_deliver(paths["session_dir"]):
            from cycle_delivered_refs import record_delivered_ref  # noqa: WPS433

            record_delivered_ref(
                cycle_id,
                project_root,
                delivered_type=stage,
                path=str(doc_path.resolve()),
                revision=1,
                profile_id=stage,
                source_workflow_state=str(ss_path.resolve()),
            )
        write_session_state(ss_path, "Completed")
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit(
        {
            "ok": True,
            "session_state": "Completed",
            "session_state_path": ss_path.as_posix(),
            "decision_doc_path": doc_path.as_posix(),
        }
    )
    return 0


def cmd_prepare(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    """Verify delivery-ready + decision-doc without changing session state."""
    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    frozen = _reject_if_frozen(paths)
    if frozen is not None:
        return frozen
    try:
        state = load_gate_state(paths["gate_state"])
        if not is_gate_closed(state, "DC"):
            return _emit_error("DC gate must be closed before prepare")
        reg_flags = _register_io_flags(state)
        reg_flags["r_gate_closed"] = True
        registers = load_registers(paths["registers"], **reg_flags)
        errors = _collect_delivery_errors(
            project_root,
            cycle_id,
            stage,
            state,
            registers,
            paths,
            constraints_path=constraints_path,
            require_decision_doc=True,
        )
        if errors:
            return _emit_error("; ".join(errors))
        doc_path = paths["decision_doc"]
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, "decision_doc_path": doc_path.as_posix()})
    return 0


def cmd_deliver(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    """Deprecated alias for ``complete`` (node/session terminal)."""
    return cmd_complete(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )


def cmd_gate_close(
    project_root: Path,
    cycle_id: str,
    stage: str,
    gate: str,
    payload: dict[str, Any],
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    frozen = _reject_if_frozen(paths)
    if frozen is not None:
        return frozen
    if gate == "RR":
        return _emit_error("RR retired; use R handle + complete-assumption")
    try:
        state = load_gate_state(paths["gate_state"])
        rr_err = _reject_if_legacy_rr_active(state)
        if rr_err:
            return _emit_error(rr_err)
        constraints = _load_session_constraints(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
            paths=paths,
        )
        prereq_error = _validate_gate_close_prereqs(state, gate)
        if prereq_error:
            return _emit_error(prereq_error)
        _validate_gate_close_payload(gate, payload, constraints=constraints)
        if gate == "R":
            exit_path = str(payload.get("exit", "")).strip()
            r_status = str(state["gates"]["R"].get("status", "")).lower()
            if r_status == "stale" and exit_path == "dc":
                review_registers = load_registers(
                    paths["registers"],
                    **_register_io_flags(state),
                )
                _validate_stale_r_review(payload, review_registers)
            if payload.get("assumptions"):
                _apply_r_register_updates(
                    paths["registers"], payload, gate_state=state
                )
            elif exit_path == "dc":
                reg_flags = _register_io_flags(state)
                reg_flags["r_gate_closed"] = True
                save_registers(
                    paths["registers"],
                    load_registers(paths["registers"], **reg_flags),
                    **reg_flags,
                )
            if exit_path == "rs":
                updated = state
            elif exit_path == "human_decision":
                updated = close_gate_r(state, exit_path="human_decision")
            else:
                reg_flags = _register_io_flags(state)
                reg_flags["r_gate_closed"] = True
                registers = load_registers(paths["registers"], **reg_flags)
                _validate_open_risk_states_for_dc(registers)
                _apply_r_prior_signoff(paths["registers"], gate_state=state)
                updated = close_gate_r(state, exit_path="dc")
        elif gate == "O":
            updated = close_gate(state, gate)
        elif gate == "DC":
            reg_flags = _register_io_flags(state)
            reg_flags["r_gate_closed"] = True
            registers = load_registers(paths["registers"], **reg_flags)
            errors = _collect_delivery_errors(
                project_root,
                cycle_id,
                stage,
                state,
                registers,
                paths,
                constraints_path=constraints_path,
                require_decision_doc=True,
            )
            if errors:
                return _emit_error("; ".join(errors))
            updated = close_gate(state, gate)
        else:
            updated = close_gate(state, gate)
        save_gate_state(paths["gate_state"], updated)
        if _gate_close_persists_payload(gate, payload):
            _persist_gate_payload(paths, gate, payload)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    result: dict[str, Any] = {
        "ok": True,
        "gate": gate,
        "status": "active"
        if gate == "R" and payload.get("exit") in {"rs", "human_decision"}
        else "closed",
        "active_gate": updated["active_gate"],
    }
    if gate == "R":
        result["exit"] = payload.get("exit")
    if gate == "R" and payload.get("exit") == "rs":
        result["realign_gate"] = payload.get("realign_gate") or payload.get(
            "reopen_gate"
        )
    if gate == "R" and payload.get("exit") == "dc":
        result["skipped_gates"] = updated.get("skipped_gates", [])
    _emit(result)
    return 0


def _prepare_stale_from(
    paths: dict[str, Path],
    gate: str,
) -> dict[str, Any]:
    """Validate and compute a stale sweep without persisting."""
    state = load_gate_state(paths["gate_state"])
    if gate not in GATE_ORDER:
        raise ValueError(f"invalid gate: {gate!r}")
    if gate not in RS_REALIGN_GATES:
        raise ValueError(
            f"stale-from / rs-commit supports {list(RS_REALIGN_GATES)}, got {gate!r}"
        )
    return mark_stale_from_gate(state, gate)


def _run_stale_from(
    paths: dict[str, Path],
    gate: str,
) -> dict[str, Any]:
    """Mark G + reached downstream stale; keep payloads and Register facts."""
    updated = _prepare_stale_from(paths, gate)
    save_gate_state(paths["gate_state"], updated)
    # Update-only: do not delete_payloads_from
    return updated


def cmd_get_payload(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    gates: list[str] | None = None,
    stale_only: bool = False,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    """Read persisted gate-payloads; never invent from memory."""
    if not stale_only and not gates:
        return _emit_error("get-payload requires --gate/--gates or --stale-only")
    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    try:
        state = load_gate_state(paths["gate_state"])
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    if stale_only:
        requested = [
            gate
            for gate in GATE_ORDER
            if str(state["gates"].get(gate, {}).get("status", "")).lower() == "stale"
        ]
    else:
        requested = list(gates or [])
        for gate in requested:
            if gate not in GATE_ORDER:
                return _emit_error(f"invalid gate: {gate!r}")

    payloads: dict[str, Any] = {}
    missing: list[str] = []
    for gate in requested:
        path = gate_payload_path(paths["payloads_dir"], gate)
        if path.exists():
            try:
                payloads[gate] = load_gate_payload(path)
            except (FileNotFoundError, ValueError) as exc:
                return _emit_error(str(exc))
        else:
            missing.append(gate)

    _emit({"ok": True, "payloads": payloads, "missing": missing, "requested": requested})
    return 0


def cmd_batch_reclose(
    project_root: Path,
    cycle_id: str,
    stage: str,
    payloads: dict[str, Any],
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    """Atomically re-close a consecutive stale prefix of align gates (Q/GL/E/D/X)."""
    if not isinstance(payloads, dict) or not payloads:
        return _emit_error("payloads must be a non-empty JSON object (gate -> payload)")

    unknown = sorted(set(payloads) - set(GATE_ORDER))
    if unknown:
        return _emit_error(f"unknown gates in payloads: {unknown}")

    ordered = [gate for gate in GATE_ORDER if gate in payloads]
    if set(ordered) != set(payloads):
        return _emit_error("payloads keys must be gate ids")

    for gate in ordered:
        if gate not in RS_REALIGN_GATES:
            return _emit_error(
                f"batch-reclose only supports {list(RS_REALIGN_GATES)}, got {gate!r}"
            )
        if not isinstance(payloads[gate], dict):
            return _emit_error(f"payload for {gate} must be a JSON object")

    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    frozen = _reject_if_frozen(paths)
    if frozen is not None:
        return frozen
    try:
        state = load_gate_state(paths["gate_state"])
        constraints = _load_session_constraints(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
            paths=paths,
        )
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    if ordered[0] != state["active_gate"]:
        return _emit_error(
            f"batch-reclose must start at active_gate {state['active_gate']!r}, got {ordered[0]!r}"
        )

    start = GATE_ORDER.index(ordered[0])
    expected = list(GATE_ORDER[start : start + len(ordered)])
    if ordered != expected:
        return _emit_error(
            f"batch-reclose requires consecutive GATE_ORDER prefix from active_gate; "
            f"got {ordered}, expected {expected}"
        )

    for gate in ordered:
        status = str(state["gates"].get(gate, {}).get("status", "")).lower()
        if status != "stale":
            return _emit_error(f"gate {gate} must be stale for batch-reclose (got {status!r})")

    try:
        for gate in ordered:
            _validate_gate_close_payload(
                gate, payloads[gate], constraints=constraints
            )
        updated = state
        for gate in ordered:
            prereq_error = _validate_gate_close_prereqs(updated, gate)
            if prereq_error:
                return _emit_error(prereq_error)
            updated = close_gate(updated, gate)
    except ValueError as exc:
        return _emit_error(str(exc))

    # Validate fully before any write (atomic batch).
    for gate in ordered:
        _persist_gate_payload(paths, gate, payloads[gate])
    save_gate_state(paths["gate_state"], updated)

    _emit(
        {
            "ok": True,
            "closed": ordered,
            "active_gate": updated["active_gate"],
        }
    )
    return 0


def cmd_stale_from(
    project_root: Path,
    cycle_id: str,
    stage: str,
    gate: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    try:
        updated = _run_stale_from(paths, gate)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, "gate": gate, "active_gate": updated["active_gate"]})
    return 0


def cmd_invalidate_from(
    project_root: Path,
    cycle_id: str,
    stage: str,
    gate: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    """Removed CLI — kept for clear migration error."""
    del project_root, cycle_id, stage, gate, constraints_path, session_dir
    return _emit_error(
        "invalidate-from is removed; use stale-from or rs-commit (Realign stale sweep)"
    )


def cmd_rs_commit(
    project_root: Path,
    cycle_id: str,
    stage: str,
    gate: str,
    *,
    operations: list[dict[str, Any]],
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    try:
        if gate not in RS_REALIGN_GATES:
            return _emit_error(
                f"rs-commit gate must be one of {list(RS_REALIGN_GATES)}, got {gate!r}"
            )
        updated = _prepare_stale_from(paths, gate)
        registers, applied, reg_flags = prepare_register_batch_operations(
            paths,
            operations=operations,
            gate_state=updated,
        )
        session_state = paths.get("session_state") or session_state_file(
            paths["session_dir"]
        )
        current_session_state: str | None = None
        if session_state.exists():
            current_session_state = read_current_state(session_state)
        next_session_state = (
            "InProgress"
            if current_session_state == "Frozen"
            else current_session_state
        )
        ctx = build_resolve_context_payload(
            project_root,
            cycle_id,
            stage,
            paths=paths,
            constraints_path=constraints_path,
            session_dir=session_dir,
            gate_state_override=updated,
            registers_override=registers,
            session_state_override=next_session_state,
        )

        save_gate_state(paths["gate_state"], updated)
        persisted_registers = save_registers(
            paths["registers"],
            registers,
            **reg_flags,
        )
        ctx["registers"] = persisted_registers
        ctx["reply_header"] = render_reply_header(updated, persisted_registers)
        # P1.5 A′: reopen path Frozen + RS_COMMIT → gate stale then unfreeze.
        # In-session G9→RS (P1.5a R1) stays InProgress — unfreeze is a no-op.
        unfroze = unfreeze_session(paths["session_dir"])
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit(
        {
            "ok": True,
            "reenter": gate,
            "applied": applied,
            "unfroze": unfroze,
            **ctx,
        }
    )
    return 0


def _reopen_authorization(constraints_path: Path | None, stage: str) -> str:
    if constraints_path is None:
        return ""
    try:
        cfg = load_constraints_config(constraints_path, stage=stage)
    except (FileNotFoundError, ValueError):
        return ""
    return str(cfg.get("reopen_authorization", "")).strip()


def _validate_reopen_permit(
    *,
    project_root: Path,
    cycle_id: str,
    stage: str,
    constraints_path: Path | None,
    active_session_dir: Path,
    permit_path: Path,
) -> tuple[Path, dict[str, Any], Path, dict[str, Any]]:
    """Validate holder permit. Returns (permit_path, permit, binding_path, binding)."""
    path = Path(permit_path).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"reopen permit not found: {path}")
    permit = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(permit, dict):
        raise ValueError("reopen permit must be a JSON object")
    if str(permit.get("kind", "")).strip() != "lulu-approach-reopen":
        raise ValueError("reopen permit kind must be lulu-approach-reopen")
    if str(permit.get("state", "")).strip() != "issued":
        raise ValueError(
            f"reopen permit state must be issued, got {permit.get('state')!r}"
        )
    if str(permit.get("cycle_id", "")).strip() != cycle_id:
        raise ValueError("reopen permit cycle_id mismatch")
    if str(permit.get("stage", "")).strip() != stage:
        raise ValueError("reopen permit stage mismatch")
    permit_session = str(permit.get("session_dir", "")).strip()
    if active_session_dir.name != permit_session and permit_session != ".":
        raise ValueError(
            f"reopen permit session_dir {permit_session!r} does not match Active "
            f"{active_session_dir.name!r}"
        )
    outer = stage_outer_root(
        project_root,
        cycle_id,
        stage,
        CACHE_DIR,
        constraints_path=constraints_path,
    )
    binding_path = outer / "node-binding.json"
    if not binding_path.is_file():
        raise ValueError("reopen permit requires approach node-binding.json")
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    if not isinstance(binding, dict):
        raise ValueError("node-binding must be a JSON object")
    if str(binding.get("binding_id", "")).strip() != str(permit.get("binding_id", "")).strip():
        raise ValueError("reopen permit binding_id does not match node-binding")
    if str(binding.get("state", "")).strip() != "reopen_pending":
        raise ValueError(
            f"node-binding state must be reopen_pending, got {binding.get('state')!r}"
        )
    return path, permit, binding_path, binding


def _mark_permit_consumed(
    permit_path: Path,
    permit: dict[str, Any],
    binding_path: Path,
    binding: dict[str, Any],
) -> dict[str, Any]:
    from dec_io import atomic_write_text  # noqa: WPS433

    permit = dict(permit)
    permit["state"] = "consumed"
    binding = dict(binding)
    binding["permit_state"] = "consumed"
    atomic_write_text(permit_path, json.dumps(permit, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(
        binding_path,
        json.dumps(binding, ensure_ascii=False, indent=2) + "\n",
    )
    return permit


def cmd_reopen(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
    permit_path: Path | str | None = None,
) -> int:
    """$DEC_REOPEN: Completed/InProgress → Frozen (P1.3 A / P1.3a A)."""
    paths = _paths(
        project_root,
        cycle_id,
        stage,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    try:
        if not paths["gate_state"].exists():
            return _emit_error("cannot reopen: gate-state missing")
        auth = _reopen_authorization(constraints_path, stage)
        permit_payload: dict[str, Any] | None = None
        pending_consume: tuple[Path, dict[str, Any], Path, dict[str, Any]] | None = None
        if auth == "holder_required":
            if not permit_path:
                return _emit_error(
                    "reopen_authorization=holder_required: --permit is required"
                )
            pending_consume = _validate_reopen_permit(
                project_root=project_root,
                cycle_id=cycle_id,
                stage=stage,
                constraints_path=constraints_path,
                active_session_dir=paths["session_dir"],
                permit_path=Path(permit_path),
            )
        prior = set_session_frozen(paths["session_dir"])
        if pending_consume is not None:
            permit_payload = _mark_permit_consumed(*pending_consume)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        return _emit_error(str(exc))

    ss_path = paths.get("session_state") or session_state_file(paths["session_dir"])
    out: dict[str, Any] = {
        "ok": True,
        "command": "reopen",
        "prior_state": prior,
        "session_state": "Frozen",
        "session_state_path": ss_path.as_posix(),
        "session_dir": paths["session_dir"].as_posix(),
        "cycle_id": cycle_id,
        "stage": stage,
    }
    if permit_payload is not None:
        out["permit_binding_id"] = permit_payload.get("binding_id")
        out["permit_state"] = "consumed"
    _emit(out)
    return 0


def cmd_migrate_session(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> int:
    if session_dir is None:
        session_dir = project_root / session_base_dir(
            cycle_id,
            stage,
            project_root=project_root,
            constraints_path=constraints_path,
        )
    paths = session_artifact_paths(Path(session_dir).resolve())
    try:
        if not needs_migration(paths["session_dir"]):
            return _emit_error("session does not require migration (gate-state exists or no session-state)")
        result = migrate_session_dir(
            paths["session_dir"],
            project_root=project_root,
            cycle_id=cycle_id,
            stage=stage,
            constraints_path=constraints_path,
        )
        from dec_active_control import _commit_active  # noqa: WPS433

        _commit_active(
            project_root,
            cycle_id,
            stage,
            session_dir=paths["session_dir"],
            constraints_path=constraints_path,
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
    parser = argparse.ArgumentParser(description="Decision gate state control.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID.")
    parser.add_argument("--stage", default="decision", help="Decision stage name.")
    parser.add_argument(
        "--constraints",
        default="",
        help="Path to holder constraints.json (required for holder stages at init).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init-session", help="Bootstrap session artifacts.")
    init_parser.add_argument(
        "--domain-constraints",
        default="",
        help="Optional JSON override for domain-constraints (omitted_sections, x_dimensions).",
    )

    sub.add_parser("resolve-context", help="Return session context JSON.")

    get_payload = sub.add_parser(
        "get-payload",
        help="Read persisted gate-payloads by gate list or --stale-only.",
    )
    get_payload.add_argument("--gate", default="", help="Single gate id.")
    get_payload.add_argument(
        "--gates",
        default="",
        help="Comma-separated gate ids (e.g. Q,GL,E).",
    )
    get_payload.add_argument(
        "--stale-only",
        action="store_true",
        help="Return payloads for all gates currently marked stale.",
    )

    activate = sub.add_parser("gate-activate", help="Activate a gate.")
    activate.add_argument("--gate", required=True)

    apply_r = sub.add_parser(
        "apply-r-assumptions",
        help="Persist R expose draft assumptions without closing R.",
    )
    apply_r.add_argument("--payload", required=True, help="JSON with assumptions array.")

    close = sub.add_parser(
        "gate-close",
        help=(
            "Close the active gate. Stale R exit=dc requires assumptions=[] "
            "and a confirmed stale_review receipt."
        ),
    )
    close.add_argument("--gate", required=True)
    close.add_argument("--payload", required=True, help="JSON payload string.")

    batch = sub.add_parser(
        "batch-reclose",
        help="Atomically re-close consecutive stale align gates (Q/GL/E/D/X).",
    )
    batch.add_argument(
        "--payloads",
        required=True,
        help="JSON object mapping gate id -> close payload.",
    )

    stale = sub.add_parser(
        "stale-from",
        help="Mark align gate + reached downstream stale (keep payloads).",
    )
    stale.add_argument("--gate", required=True)

    invalidate = sub.add_parser(
        "invalidate-from",
        help="Removed — use stale-from / rs-commit.",
    )
    invalidate.add_argument("--gate", required=True)

    rs_commit = sub.add_parser(
        "rs-commit",
        help="Prevalidate, then commit Realign stale state + register batch.",
    )
    rs_commit.add_argument(
        "--gate",
        required=True,
        help="Align gate (Q, GL, E, D, or X).",
    )
    rs_commit.add_argument(
        "--operations",
        required=True,
        help="JSON array of register batch operations (use [] if none).",
    )

    reopen = sub.add_parser(
        "reopen",
        help="Leave Completed/InProgress → Frozen ($DEC_REOPEN).",
    )
    reopen.add_argument(
        "--permit",
        default="",
        help="Holder reopen permit path (required when reopen_authorization=holder_required).",
    )
    sub.add_parser(
        "check-delivery-ready",
        help="Validate readiness for DC session completion.",
    )
    sub.add_parser(
        "prepare",
        help="Verify delivery-ready + decision-doc without changing session state.",
    )
    sub.add_parser(
        "complete",
        help="Set session-state Completed after DC closed (node/session terminal).",
    )
    sub.add_parser(
        "deliver",
        help="Deprecated alias for complete (node/session terminal).",
    )
    complete_assumption = sub.add_parser(
        "complete-assumption",
        help="Write release_terms and mark assumption risk_state=completed.",
    )
    complete_assumption.add_argument("--id", required=True, dest="entry_id")
    complete_assumption.add_argument("--release-terms", required=True)

    set_risk = sub.add_parser(
        "set-risk-state",
        help="Set assumption risk_state to ignore or open.",
    )
    set_risk.add_argument("--id", required=True, dest="entry_id")
    set_risk.add_argument("--risk-state", required=True, choices=["ignore", "open"])

    sub.add_parser("migrate-session", help="Migrate legacy session to gate-state architecture.")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    stage = args.stage.strip()
    constraints_path = _parse_constraints_path(getattr(args, "constraints", ""))
    common = {
        "constraints_path": constraints_path,
        "session_dir": None,
    }

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
            **common,
        )
    if args.command == "resolve-context":
        return cmd_resolve_context(project_root, cycle_id, stage, **common)
    if args.command == "get-payload":
        gates: list[str] = []
        single = str(getattr(args, "gate", "") or "").strip()
        multi = str(getattr(args, "gates", "") or "").strip()
        if single:
            gates.append(single)
        if multi:
            gates.extend(part.strip() for part in multi.split(",") if part.strip())
        # Deduplicate preserving order
        seen: set[str] = set()
        ordered_gates: list[str] = []
        for gate in gates:
            if gate not in seen:
                seen.add(gate)
                ordered_gates.append(gate)
        return cmd_get_payload(
            project_root,
            cycle_id,
            stage,
            gates=ordered_gates or None,
            stale_only=bool(getattr(args, "stale_only", False)),
            **common,
        )
    if args.command == "gate-activate":
        return cmd_gate_activate(
            project_root,
            cycle_id,
            stage,
            args.gate.strip(),
            **common,
        )
    if args.command == "apply-r-assumptions":
        try:
            payload = _load_payload(args.payload)
        except (json.JSONDecodeError, ValueError) as exc:
            return _emit_error(str(exc))
        return cmd_apply_r_assumptions(
            project_root,
            cycle_id,
            stage,
            payload,
            **common,
        )
    if args.command == "gate-close":
        try:
            payload = _load_payload(args.payload)
        except (json.JSONDecodeError, ValueError) as exc:
            return _emit_error(str(exc))
        return cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            args.gate.strip(),
            payload,
            **common,
        )
    if args.command == "batch-reclose":
        try:
            payloads = _load_payload(args.payloads)
        except (json.JSONDecodeError, ValueError) as exc:
            return _emit_error(str(exc))
        return cmd_batch_reclose(
            project_root,
            cycle_id,
            stage,
            payloads,
            **common,
        )
    if args.command == "stale-from":
        return cmd_stale_from(
            project_root,
            cycle_id,
            stage,
            args.gate.strip(),
            **common,
        )
    if args.command == "invalidate-from":
        return cmd_invalidate_from(
            project_root,
            cycle_id,
            stage,
            args.gate.strip(),
            **common,
        )
    if args.command == "rs-commit":
        try:
            operations_raw = json.loads(args.operations)
        except json.JSONDecodeError as exc:
            return _emit_error(f"invalid operations JSON: {exc}")
        if not isinstance(operations_raw, list):
            return _emit_error("operations must be a JSON array")
        operations = [op for op in operations_raw if isinstance(op, dict)]
        if len(operations) != len(operations_raw):
            return _emit_error("each operation must be a JSON object")
        return cmd_rs_commit(
            project_root,
            cycle_id,
            stage,
            args.gate.strip(),
            operations=operations,
            **common,
        )
    if args.command == "reopen":
        permit_raw = str(getattr(args, "permit", "") or "").strip()
        return cmd_reopen(
            project_root,
            cycle_id,
            stage,
            permit_path=Path(permit_raw).expanduser().resolve() if permit_raw else None,
            **common,
        )
    if args.command == "check-delivery-ready":
        return cmd_check_delivery_ready(project_root, cycle_id, stage, **common)
    if args.command == "prepare":
        return cmd_prepare(project_root, cycle_id, stage, **common)
    if args.command in {"complete", "deliver"}:
        return cmd_complete(project_root, cycle_id, stage, **common)
    if args.command == "complete-assumption":
        return cmd_complete_assumption(
            project_root,
            cycle_id,
            stage,
            entry_id=args.entry_id.strip(),
            release_terms=args.release_terms,
            **common,
        )
    if args.command == "set-risk-state":
        return cmd_set_risk_state(
            project_root,
            cycle_id,
            stage,
            entry_id=args.entry_id.strip(),
            risk_state=args.risk_state,
            **common,
        )
    if args.command == "migrate-session":
        return cmd_migrate_session(project_root, cycle_id, stage, **common)
    return _emit_error(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
