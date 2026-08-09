#!/usr/bin/env python3
"""Session integrity control for decision: structural audit and decision-doc render.

Resolves the Active Session root (archive-1.1), same contract as gate/register.

Subcommands:
    audit --mode structural      Validate gate-payloads + registers + gate-state
    render                       Build decision-doc.md from payloads + registers
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

from dec_decision_doc_schema import (  # noqa: E402
    init_decision_doc,
    render_direction_body,
    render_execution_analysis_body,
    render_problem_body,
    render_settled_direction_body,
    replace_section,
    save_decision_doc,
)
from dec_domain_constraints_schema import (  # noqa: E402
    KERNEL_STAGE,
    active_x_dimensions,
    load_domain_constraints,
)
from dec_gate_payload_schema import (  # noqa: E402
    gate_payload_path,
    gate_payloads_for_session,
    load_gate_payload,
)
from dec_gate_state_schema import (  # noqa: E402
    GATE_ORDER,
    is_gate_closed,
    is_gate_reached,
    load_gate_state,
)
from dec_register_schema import load_registers, validate_registers  # noqa: E402
from dec_session_paths import (  # noqa: E402
    resolve_session_root_for_command,
    session_artifact_paths,
)
from dec_workflow_common import CACHE_DIR  # noqa: E402


def _emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _emit_error(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    return 1


def _session_paths(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
    session_dir: Path | None = None,
) -> dict[str, Path]:
    """Resolve artifact paths via Active Session (archive-1.1 A3), same as gate/register."""
    root = resolve_session_root_for_command(
        project_root,
        cycle_id,
        stage,
        CACHE_DIR,
        constraints_path=constraints_path,
        session_dir=session_dir,
    )
    return session_artifact_paths(root)


def _load_constraints(paths: dict[str, Path]) -> dict[str, Any]:
    if paths["domain_constraints"].exists():
        return load_domain_constraints(paths["domain_constraints"])
    return {}


def _validate_gate_payload(gate: str, payload: dict[str, Any], *, constraints: dict[str, Any]) -> None:
    from dec_gate_control import _validate_gate_close_payload  # noqa: WPS433

    _validate_gate_close_payload(gate, payload, constraints=constraints)


def run_structural_audit(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
) -> list[str]:
    paths = _session_paths(project_root, cycle_id, stage, constraints_path=constraints_path)
    state = load_gate_state(paths["gate_state"])
    r_closed = is_gate_closed(state, "R")
    r_reached = is_gate_reached(state, "R")
    constraints = _load_constraints(paths)
    errors: list[str] = []

    registers_raw = json.loads(paths["registers"].read_text(encoding="utf-8"))
    reg_errors = validate_registers(
        registers_raw,
        r_gate_closed=r_closed,
        r_risk_fields_allowed=r_reached,
    )
    for err in reg_errors:
        if "risk fields set before R gate reached" in err:
            errors.append(f"REG_RISK_WHEN_R_OPEN: {err}")

    skipped = frozenset(state.get("skipped_gates") or [])
    for gate in GATE_ORDER:
        gate_entry = state.get("gates", {}).get(gate, {})
        status = str(gate_entry.get("status", ""))
        if status != "closed":
            continue
        if gate in skipped:
            continue
        payload_path = gate_payload_path(paths["payloads_dir"], gate)
        if not payload_path.exists():
            errors.append(f"GATE_PAYLOAD_COMPLETE: closed gate {gate} missing payload file")
            continue
        try:
            payload = load_gate_payload(payload_path)
            _validate_gate_payload(gate, payload, constraints=constraints)
        except ValueError as exc:
            errors.append(f"PAYLOAD_SCHEMA_VALID: gate {gate}: {exc}")

    return errors


def _apply_payload_to_doc(
    doc: str,
    gate: str,
    payload: dict[str, Any],
    *,
    constraints: dict[str, Any],
) -> str:
    if gate == "Q":
        body = render_problem_body(
            problem_statement=str(payload.get("problem_statement", "")),
            constraints=str(payload.get("constraints", "")),
        )
        return replace_section(doc, "problem", body, constraints=constraints)
    if gate == "E":
        directions = payload.get("directions", [])
        excluded = payload.get("excluded", [])
        if not isinstance(excluded, list):
            excluded = []
        body = render_direction_body(
            directions=directions,
            excluded=excluded,
            user_choice=str(payload.get("user_choice", "")).strip(),
        )
        return replace_section(doc, "direction", body, constraints=constraints)
    if gate == "D":
        return replace_section(
            doc,
            "settled_direction",
            render_settled_direction_body(
                rationale=str(payload.get("decision_rationale", "")),
                applies_to=str(payload.get("applies_to", "")),
                excludes=str(payload.get("excludes", "")),
                execution_approach=str(payload.get("execution_approach", "")),
            ),
            constraints=constraints,
        )
    if gate == "X":
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
        return replace_section(doc, "execution_analysis", body, constraints=constraints)
    return doc


def render_decision_doc(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
) -> Path:
    paths = _session_paths(project_root, cycle_id, stage, constraints_path=constraints_path)
    constraints = _load_constraints(paths)
    template = fetch_template("decision", "decision_doc_template_url", project_root)
    doc = init_decision_doc(template=template, cycle_id=cycle_id, constraints=constraints)

    payloads = gate_payloads_for_session(paths["payloads_dir"])
    for gate in ("Q", "E", "D", "X"):
        payload = payloads.get(gate)
        if payload is not None:
            doc = _apply_payload_to_doc(doc, gate, payload, constraints=constraints)

    from dec_register_control import sync_registers_to_doc  # noqa: WPS433

    save_decision_doc(paths["decision_doc"], doc)
    state = load_gate_state(paths["gate_state"])
    r_closed = is_gate_closed(state, "R")
    sync_registers_to_doc(
        paths["decision_doc"],
        paths["registers"],
        r_gate_closed=r_closed,
        constraints=constraints,
    )
    return paths["decision_doc"]


def cmd_audit(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    mode: str,
    constraints_path: Path | None = None,
) -> int:
    if mode != "structural":
        return _emit_error(f"unsupported audit mode: {mode!r}")
    try:
        errors = run_structural_audit(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
        )
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, "mode": mode, "errors": errors, "passed": not errors})
    return 0


def cmd_render(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    constraints_path: Path | None = None,
) -> int:
    try:
        doc_path = render_decision_doc(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
        )
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))

    _emit({"ok": True, "decision_doc_path": doc_path.as_posix()})
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Decision session integrity control.")
    parser.add_argument("--project-root", default=".", help="Project root directory.")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID.")
    parser.add_argument("--stage", default=KERNEL_STAGE, help="Decision stage name.")
    parser.add_argument("--constraints", default="", help="Path to holder constraints.json.")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="Run session integrity audit.")
    audit.add_argument(
        "--mode",
        default="structural",
        help="Audit mode: structural.",
    )

    sub.add_parser("render", help="Render decision-doc.md from gate-payloads.")

    return parser.parse_args(argv)


def _parse_constraints_path(raw: str) -> Path | None:
    text = raw.strip()
    if not text:
        return None
    return Path(text).expanduser().resolve()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    stage = args.stage.strip()
    constraints_path = _parse_constraints_path(getattr(args, "constraints", ""))

    if args.command == "audit":
        return cmd_audit(
            project_root,
            cycle_id,
            stage,
            mode=args.mode.strip(),
            constraints_path=constraints_path,
        )
    if args.command == "render":
        return cmd_render(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
        )
    return _emit_error(f"unknown command: {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
