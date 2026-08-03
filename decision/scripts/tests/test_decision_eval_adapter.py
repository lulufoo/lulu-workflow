#!/usr/bin/env python3
"""Tests for Decision Eval adapter + registry + fail/pass exit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_EVAL_ADAPTER = _SCRIPTS / "eval"
_EVAL_SCRIPTS = Path(__file__).resolve().parents[3] / "eval" / "scripts"
for p in (_SCRIPTS, _EVAL_ADAPTER, _EVAL_SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from decision_eval_adapter import DecisionEvalAdapter  # noqa: E402
import io
from contextlib import redirect_stdout

from dec_eval_control import cmd_check_rounds, cmd_fail_exit, cmd_pass_exit  # noqa: E402
from dec_eval_runtime_schema import load_runtime, runtime_path  # noqa: E402
from dec_eval_target_schema import EVAL_TARGET_FILENAME  # noqa: E402
from dec_gate_payload_schema import save_gate_payload  # noqa: E402
from dec_gate_state_schema import GATE_ORDER, init_gate_state, save_gate_state  # noqa: E402
from dec_register_schema import init_registers, save_registers  # noqa: E402
from dec_session_state_schema import write_session_state  # noqa: E402
from dec_workflow_common import CACHE_DIR  # noqa: E402
from eval_adapter_config import load_eval_adapter_from_config  # noqa: E402
from eval_handoff_schema import validate_eval_handoff_v2  # noqa: E402


def _run_json(fn, *args, **kwargs) -> dict:
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = fn(*args, **kwargs)
    payload = json.loads(buf.getvalue())
    assert code == (0 if payload.get("ok") else 1)
    return payload


def _seed_dc_session(project_root: Path, cycle_id: str) -> Path:
    session = project_root / CACHE_DIR / cycle_id / "decision"
    session.mkdir(parents=True)
    write_session_state(session / "session-state.md", "InProgress")
    (session / "domain-constraints.json").write_text(
        json.dumps(
            {
                "version": "1",
                "stage": "decision",
                "cache_subdir": "decision",
                "omitted_sections": [],
                "x_dimensions": [
                    "acceptance_criteria",
                    "impact_surface",
                    "external_dependencies",
                    "implementation_sketch",
                    "gap_check",
                ],
            }
        ),
        encoding="utf-8",
    )
    state = init_gate_state(cycle_id=cycle_id, stage="decision")
    for gate in GATE_ORDER:
        if gate == "DC":
            state["gates"][gate]["status"] = "active"
            state["active_gate"] = "DC"
        elif gate in ("V", "RR"):
            state["gates"][gate]["status"] = "skipped"
        else:
            state["gates"][gate]["status"] = "closed"
    state["skipped_gates"] = ["V", "RR"]
    save_gate_state(session / "gate-state.json", state)

    payloads = session / "gate-payloads"
    payloads.mkdir()
    save_gate_payload(
        payloads / "Q.json",
        {"problem_statement": "P", "constraints": "C"},
    )
    save_gate_payload(
        payloads / "E.json",
        {
            "directions": [{"name": "A", "approach": "a", "pros": "p", "cons": "c"}],
            "excluded": [],
            "user_choice": "A",
        },
    )
    save_gate_payload(
        payloads / "D.json",
        {
            "decision_rationale": "choose A",
            "applies_to": "all",
            "excludes": "none",
            "execution_approach": "phase-1 ship",
        },
    )
    save_gate_payload(
        payloads / "X.json",
        {
            "acceptance_criteria": "phase-1 done",
            "gap": "None",
            "impact_surface": [],
            "external_dependencies": [],
            "key_changes": "k",
            "critical_constraints": "c",
            "reversibility": "yes",
        },
    )
    # O/GL/R also closed — empty-ish payloads ok for bind completeness (Q/E/D/X only)
    for gate in ("O", "GL", "R"):
        save_gate_payload(payloads / f"{gate}.json", {"note": "closed"})
    save_registers(
        session / "registers.json",
        init_registers(cycle_id=cycle_id, stage="decision"),
        r_gate_closed=True,
    )
    return session


def test_profile_config_loads_decision_adapter() -> None:
    profile = (
        Path(__file__).resolve().parents[2] / "eval" / "eval-profile.json"
    )
    adapter = load_eval_adapter_from_config(profile)
    assert adapter.__class__.__name__ == "DecisionEvalAdapter"


def test_enter_evaluating_binds_target_and_handoff(tmp_path: Path) -> None:
    cycle_id = "feature-dec-eval-1"
    session = _seed_dc_session(tmp_path, cycle_id)
    adapter = DecisionEvalAdapter()

    entered = adapter.enter_evaluating(cycle_id, tmp_path)
    assert entered["ok"] is True
    assert (session / EVAL_TARGET_FILENAME).is_file()
    assert "choose A" in (session / EVAL_TARGET_FILENAME).read_text(encoding="utf-8")

    handoff = adapter.request_eval_handoff(cycle_id, tmp_path, require_evaluating=True)
    errors = validate_eval_handoff_v2(handoff)
    assert errors == []
    assert handoff["context"]["workflow_id"] == "lulu-decision"
    assert handoff["context"]["session_key"] == "DC"
    assert EVAL_TARGET_FILENAME in handoff["context"]["bindings"]["eval_target_path"]


def test_fail_exit_sets_realign_and_hard_block(tmp_path: Path) -> None:
    cycle_id = "feature-dec-eval-2"
    _seed_dc_session(tmp_path, cycle_id)
    adapter = DecisionEvalAdapter()
    assert adapter.enter_evaluating(cycle_id, tmp_path)["ok"] is True

    fail1 = _run_json(
        cmd_fail_exit,
        tmp_path,
        cycle_id,
        "decision",
        issues=[
            {
                "dimension_id": "decision-consistency",
                "realign_gate": "E",
                "location": "settled_direction",
                "description": "mismatch",
            }
        ],
    )
    assert fail1["realign_gate"] == "E"
    runtime = load_runtime(runtime_path(tmp_path / CACHE_DIR / cycle_id / "decision"))
    assert runtime["focus_phase"] == "pending"
    assert runtime["failure_count"] == 1

    assert adapter.enter_evaluating(cycle_id, tmp_path)["ok"] is True
    _run_json(
        cmd_fail_exit,
        tmp_path,
        cycle_id,
        "decision",
        issues=[
            {
                "dimension_id": "decision-consistency",
                "realign_gate": "D",
                "description": "phase",
            }
        ],
    )
    payload = _run_json(cmd_check_rounds, tmp_path, cycle_id, "decision")
    assert payload["hard_blocked"] is True
    assert payload["failure_count"] == 2

    blocked = adapter.enter_evaluating(cycle_id, tmp_path)
    assert blocked["ok"] is False
    assert "hard-blocked" in blocked["error"]


def test_pass_exit_resets_failure_count(tmp_path: Path) -> None:
    cycle_id = "feature-dec-eval-3"
    _seed_dc_session(tmp_path, cycle_id)
    adapter = DecisionEvalAdapter()
    assert adapter.enter_evaluating(cycle_id, tmp_path)["ok"] is True
    _run_json(
        cmd_fail_exit,
        tmp_path,
        cycle_id,
        "decision",
        issues=[
            {
                "dimension_id": "decision-consistency",
                "realign_gate": "X",
                "description": "g",
            }
        ],
    )
    assert adapter.enter_evaluating(cycle_id, tmp_path)["ok"] is True
    payload = _run_json(cmd_pass_exit, tmp_path, cycle_id, "decision")
    assert payload["outcome"] == "pass"
    assert payload["failure_count"] == 0
