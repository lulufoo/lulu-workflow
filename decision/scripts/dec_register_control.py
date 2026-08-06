#!/usr/bin/env python3
"""Register control for decision sessions.

Subcommands:
    register-append        Append prior or assumption entry (G0 capture)
    register-commit        Atomic G0: append/update ops + full session context
    register-update        Update an existing register entry
    register-batch-apply   RS batch labeling and deletions
    sync-registers-to-doc  Render registers into decision-doc sections
    resolve-context        Register-focused context JSON (reply_header always empty)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dec_decision_doc_schema import (
    is_section_active,
    load_decision_doc,
    render_assumptions_body,
    render_user_prior_body,
    replace_section,
    save_decision_doc,
)
from dec_domain_constraints_schema import load_domain_constraints
from dec_gate_state_schema import is_gate_closed, load_gate_state
from dec_register_schema import (
    PRIOR_KINDS,
    REGISTER_STATES,
    RISK_CLASSES,
    RISK_LEVELS,
    RISK_STATES,
    find_duplicate_assumption,
    find_duplicate_prior,
    load_registers,
    next_assumption_id,
    next_prior_id,
    save_registers,
)
from dec_session_paths import resolve_session_root_for_command, session_artifact_paths
from dec_session_render import render_reply_header
from dec_workflow_common import CACHE_DIR


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _emit_error(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    return 1


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


def _register_io_flags(gate_state: dict[str, Any]) -> dict[str, bool]:
    active = str(gate_state.get("active_gate", ""))
    r_closed = is_gate_closed(gate_state, "R")
    allowed = active == "R" or r_closed
    return {"r_gate_closed": r_closed, "r_risk_fields_allowed": allowed}


def _active_register_source(gate_state: dict[str, Any]) -> str:
    active = str(gate_state.get("active_gate", "O"))
    if active == "O":
        return "O"
    if active == "V":
        return "R"
    if active in {"Q", "GL", "E", "D", "X", "R"}:
        return active
    return "O"


def sync_registers_to_doc(
    decision_doc_file: Path,
    registers_file: Path,
    *,
    r_gate_closed: bool,
    constraints: dict[str, Any] | None = None,
) -> None:
    if constraints is None:
        constraints_path = decision_doc_file.parent / "domain-constraints.json"
        if constraints_path.exists():
            constraints = load_domain_constraints(constraints_path)
    gate_state_path = decision_doc_file.parent / "gate-state.json"
    reg_flags = {"r_gate_closed": r_gate_closed, "r_risk_fields_allowed": r_gate_closed}
    if gate_state_path.exists():
        gate_state = load_gate_state(gate_state_path)
        reg_flags = _register_io_flags(gate_state)
    registers = load_registers(registers_file, **reg_flags)
    doc = load_decision_doc(decision_doc_file)
    if constraints is None or is_section_active(constraints, "user_prior"):
        doc = replace_section(doc, "user_prior", render_user_prior_body(registers), constraints=constraints)
    if constraints is None or is_section_active(constraints, "assumptions"):
        doc = replace_section(doc, "assumptions", render_assumptions_body(registers), constraints=constraints)
    save_decision_doc(decision_doc_file, doc)


def _apply_append_operation(
    registers: dict[str, Any],
    *,
    register_kind: str,
    payload: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    if register_kind == "prior":
        kind = str(payload.get("kind", "")).strip()
        text = str(payload.get("text", "")).strip()
        if kind not in PRIOR_KINDS:
            raise ValueError(f"invalid prior kind: {kind!r}")
        if not text:
            raise ValueError("text is required")
        duplicate = find_duplicate_prior(registers, kind=kind, text=text)
        if duplicate:
            return duplicate
        entry_id = next_prior_id(registers)
        entry = {
            "id": entry_id,
            "kind": kind,
            "text": text,
            "state": "pending",
            "source": source,
            "created_at": _now_iso(),
        }
        registers["prior"].append(entry)
        registers["next_prior_seq"] = int(registers.get("next_prior_seq", 1)) + 1
        return entry
    if register_kind == "assumption":
        text = str(payload.get("text", "")).strip()
        if not text:
            raise ValueError("text is required")
        duplicate = find_duplicate_assumption(registers, text)
        if duplicate:
            return duplicate
        entry_id = next_assumption_id(registers)
        entry = {
            "id": entry_id,
            "text": text,
            "source": source,
            "created_at": _now_iso(),
        }
        registers["assumptions"].append(entry)
        registers["next_assumption_seq"] = int(registers.get("next_assumption_seq", 1)) + 1
        return entry
    raise ValueError(f"invalid register kind: {register_kind!r}")


def _apply_update_operation(
    registers: dict[str, Any],
    *,
    entry_id: str,
    payload: dict[str, Any],
    r_closed: bool,
    r_risk_fields_allowed: bool | None = None,
) -> dict[str, Any]:
    if r_risk_fields_allowed is None:
        r_risk_fields_allowed = r_closed
    target = _find_entry(registers, entry_id)
    if target is None:
        raise ValueError(f"entry not found: {entry_id}")

    is_assumption = str(target.get("id", "")).startswith("A")

    if "state" in payload:
        if is_assumption:
            raise ValueError("assumption.state retired; use risk_state")
        state = str(payload["state"])
        if state not in REGISTER_STATES:
            raise ValueError(f"invalid state: {state!r}")
        target["state"] = state

    if "text" in payload:
        text = str(payload["text"]).strip()
        if not text:
            raise ValueError("text must be non-empty")
        target["text"] = text

    risk_field_map = {
        "risk_level": RISK_LEVELS,
        "risk_class": RISK_CLASSES,
        "risk_state": RISK_STATES,
    }
    for field, allowed in risk_field_map.items():
        if field in payload:
            if not is_assumption:
                raise ValueError(f"{field} only valid on assumptions")
            if not r_risk_fields_allowed:
                raise ValueError(f"{field} cannot be set before R gate is reached")
            value = payload[field]
            if value is not None and str(value).strip() not in allowed:
                raise ValueError(f"invalid {field}: {value!r}")
            normalized = None if value is None else str(value).strip()
            if field == "risk_state" and normalized == "completed":
                raise ValueError(
                    "risk_state=completed only via complete-assumption "
                    "(not register-update)"
                )
            target[field] = normalized

    for field in ("risk_consequence", "release_terms"):
        if field in payload:
            if not is_assumption:
                raise ValueError(f"{field} only valid on assumptions")
            if not r_risk_fields_allowed:
                raise ValueError(f"{field} cannot be set before R gate is reached")
            target[field] = payload[field]

    for retired in ("risk", "consequence", "verification", "disposition", "release_tracking", "released"):
        if retired in payload:
            raise ValueError(f"{retired} retired")

    return target


def apply_register_commit_operations(
    paths: dict[str, Path],
    *,
    operations: list[dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    """Apply G0 append/update ops; persist registers once."""
    gate_state = load_gate_state(paths["gate_state"])
    reg_flags = _register_io_flags(gate_state)
    registers = load_registers(paths["registers"], **reg_flags)
    source = _active_register_source(gate_state)
    applied = 0

    for op in operations:
        action = str(op.get("action", "")).strip()
        if action == "append":
            kind = str(op.get("kind", "")).strip()
            payload = op.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("append operation requires object payload")
            _apply_append_operation(registers, register_kind=kind, payload=payload, source=source)
            applied += 1
        elif action == "update":
            entry_id = str(op.get("id", "")).strip()
            payload = op.get("payload")
            if not entry_id:
                raise ValueError("update operation requires id")
            if not isinstance(payload, dict):
                raise ValueError("update operation requires object payload")
            _apply_update_operation(
                registers,
                entry_id=entry_id,
                payload=payload,
                r_closed=reg_flags["r_gate_closed"],
                r_risk_fields_allowed=reg_flags["r_risk_fields_allowed"],
            )
            applied += 1
        else:
            raise ValueError(f"invalid action: {action!r} (use append or update)")

    save_registers(paths["registers"], registers, **reg_flags)
    return registers, applied


def cmd_register_commit(
    project_root: Path,
    cycle_id: str,
    stage: str,
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
        _, applied = apply_register_commit_operations(paths, operations=operations)
        from dec_gate_control import build_resolve_context_payload  # noqa: WPS433

        ctx = build_resolve_context_payload(
            project_root,
            cycle_id,
            stage,
            paths=paths,
            constraints_path=constraints_path,
            session_dir=session_dir,
        )
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, "applied": applied, **ctx})
    return 0


def cmd_register_append(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    register_kind: str,
    payload: dict[str, Any],
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
        gate_state = load_gate_state(paths["gate_state"])
        reg_flags = _register_io_flags(gate_state)
        registers = load_registers(paths["registers"], **reg_flags)
        source = _active_register_source(gate_state)
        entry = _apply_append_operation(
            registers,
            register_kind=register_kind,
            payload=payload,
            source=source,
        )
        save_registers(paths["registers"], registers, **reg_flags)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, "entry": entry, "source": source})
    return 0


def cmd_register_update(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    entry_id: str,
    payload: dict[str, Any],
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
        gate_state = load_gate_state(paths["gate_state"])
        reg_flags = _register_io_flags(gate_state)
        registers = load_registers(paths["registers"], **reg_flags)
        target = _apply_update_operation(
            registers,
            entry_id=entry_id,
            payload=payload,
            r_closed=reg_flags["r_gate_closed"],
            r_risk_fields_allowed=reg_flags["r_risk_fields_allowed"],
        )
        save_registers(paths["registers"], registers, **reg_flags)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, "entry": target})
    return 0


def _find_entry(registers: dict[str, Any], entry_id: str) -> dict[str, Any] | None:
    for collection in ("prior", "assumptions"):
        for entry in registers.get(collection, []):
            if isinstance(entry, dict) and str(entry.get("id")) == entry_id:
                return entry
    return None


def apply_register_batch_operations(
    paths: dict[str, Path],
    *,
    operations: list[dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    """Apply RS batch ops; persist registers. Returns (registers, applied)."""
    gate_state = load_gate_state(paths["gate_state"])
    reg_flags = _register_io_flags(gate_state)
    registers = load_registers(paths["registers"], **reg_flags)

    for op in operations:
        entry_id = str(op.get("id", ""))
        action = str(op.get("action", ""))
        target = _find_entry(registers, entry_id)
        if target is None:
            raise ValueError(f"entry not found: {entry_id}")
        if action == "delete":
            collection = "prior" if entry_id.startswith("P") else "assumptions"
            registers[collection] = [
                e for e in registers[collection] if str(e.get("id")) != entry_id
            ]
        elif action == "set_state":
            state = str(op.get("state", ""))
            if state not in REGISTER_STATES:
                raise ValueError(f"invalid state: {state!r}")
            if state == "invalidated":
                collection = "prior" if entry_id.startswith("P") else "assumptions"
                registers[collection] = [
                    e for e in registers[collection] if str(e.get("id")) != entry_id
                ]
            elif entry_id.startswith("A"):
                raise ValueError("assumption.state retired; use risk_state")
            else:
                target["state"] = state
        else:
            raise ValueError(f"invalid action: {action!r}")

    save_registers(paths["registers"], registers, **reg_flags)
    return registers, len(operations)


def cmd_register_batch_apply(
    project_root: Path,
    cycle_id: str,
    stage: str,
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
        _, applied = apply_register_batch_operations(paths, operations=operations)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, "applied": applied})
    return 0


def cmd_sync_registers(
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
        gate_state = load_gate_state(paths["gate_state"])
        r_closed = is_gate_closed(gate_state, "R")
        sync_registers_to_doc(paths["decision_doc"], paths["registers"], r_gate_closed=r_closed)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))
    _emit({"ok": True})
    return 0


def cmd_resolve_context(
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
        gate_state = load_gate_state(paths["gate_state"])
        reg_flags = _register_io_flags(gate_state)
        registers = load_registers(paths["registers"], **reg_flags)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit(
        {
            "ok": True,
            "registers_path": paths["registers"].as_posix(),
            "decision_doc_path": paths["decision_doc"].as_posix(),
            "active_gate": gate_state["active_gate"],
            "registers": registers,
            "reply_header": render_reply_header(gate_state, registers),
        }
    )
    return 0


def _load_payload(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("payload must be a JSON object")
    return data


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Decision register control.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID.")
    parser.add_argument("--stage", default="decision", help="Decision stage name.")
    parser.add_argument(
        "--constraints",
        default="",
        help="Path to holder constraints.json (for session path resolution before snapshot exists).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    append = sub.add_parser(
        "register-append",
        help="Append a register entry (G0 capture).",
        description=(
            "Append User Prior or Assumption. Sets source from active_gate, assigns id, "
            "dedupes by kind+text (prior) or text (assumption).\n\n"
            "Prior payload: {\"kind\": \"judgment|preference|concern|excluded\", \"text\": \"...\"}\n"
            "Assumption payload: {\"text\": \"...\"}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    append.add_argument("--kind", required=True, choices=["prior", "assumption"])
    append.add_argument("--payload", required=True, help="JSON payload string.")

    update = sub.add_parser("register-update", help="Update a register entry.")
    update.add_argument("--id", required=True, dest="entry_id")
    update.add_argument("--payload", required=True, help="JSON payload string.")

    batch = sub.add_parser("register-batch-apply", help="Apply RS batch operations.")
    batch.add_argument("--operations", required=True, help="JSON array string.")

    commit = sub.add_parser(
        "register-commit",
        help="Atomic G0: append/update operations + sync + full session context.",
        description=(
            "Apply one or more register writes, return full session context.\n\n"
            "Operations JSON array examples:\n"
            '  [{"action":"append","kind":"prior","payload":{"kind":"preference","text":"..."}}]\n'
            '  [{"action":"append","kind":"assumption","payload":{"text":"..."}}]\n'
            '  [{"action":"update","id":"P1","payload":{"text":"revised"}}]\n'
            "Multiple ops in one array are allowed (e.g. prior + assumption in one G0 turn)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commit.add_argument("--operations", required=True, help="JSON array of append/update operations.")

    sub.add_parser("sync-registers-to-doc", help="Render registers into decision-doc.")
    sub.add_parser("resolve-context", help="Return register context JSON.")

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    stage = args.stage.strip()
    constraints_path = (
        Path(args.constraints.strip()).expanduser().resolve()
        if args.constraints.strip()
        else None
    )
    common = {
        "constraints_path": constraints_path,
        "session_dir": None,
    }

    if args.command == "register-append":
        try:
            payload = _load_payload(args.payload)
        except (json.JSONDecodeError, ValueError) as exc:
            return _emit_error(str(exc))
        return cmd_register_append(
            project_root,
            cycle_id,
            stage,
            register_kind=args.kind.strip(),
            payload=payload,
            **common,
        )
    if args.command == "register-update":
        try:
            payload = _load_payload(args.payload)
        except (json.JSONDecodeError, ValueError) as exc:
            return _emit_error(str(exc))
        return cmd_register_update(
            project_root,
            cycle_id,
            stage,
            entry_id=args.entry_id.strip(),
            payload=payload,
            **common,
        )
    if args.command == "register-batch-apply":
        try:
            operations = json.loads(args.operations)
        except json.JSONDecodeError as exc:
            return _emit_error(str(exc))
        if not isinstance(operations, list):
            return _emit_error("operations must be a JSON array")
        return cmd_register_batch_apply(
            project_root,
            cycle_id,
            stage,
            operations=operations,
            **common,
        )
    if args.command == "register-commit":
        try:
            operations = json.loads(args.operations)
        except json.JSONDecodeError as exc:
            return _emit_error(str(exc))
        if not isinstance(operations, list):
            return _emit_error("operations must be a JSON array")
        cleaned = [op for op in operations if isinstance(op, dict)]
        if len(cleaned) != len(operations):
            return _emit_error("each operation must be a JSON object")
        return cmd_register_commit(
            project_root,
            cycle_id,
            stage,
            operations=cleaned,
            **common,
        )
    if args.command == "sync-registers-to-doc":
        return cmd_sync_registers(
            project_root,
            cycle_id,
            stage,
            **common,
        )
    if args.command == "resolve-context":
        return cmd_resolve_context(
            project_root,
            cycle_id,
            stage,
            **common,
        )
    return _emit_error(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
