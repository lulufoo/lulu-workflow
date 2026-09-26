#!/usr/bin/env python3
"""G5 retirement: reverse/restart cleanup and incompatible continue."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bootstrap  # noqa: F401
import pytest

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
if str(_INDUCTIVE_DIR) not in sys.path:
    sys.path.insert(0, str(_INDUCTIVE_DIR))

import l_step_control
from inductive_gate_state_schema import (
    close_gate,
    init_gate_state,
    load_gate_state,
)
from init_working_helpers import seed_resolved_refs_for_eval
from l_ledger_schema import build_ledger, load_l_ledger, save_l_ledger
from opens_schema import opens_path
from scope_package_schema import build_scope_package, save_scope_package, write_source_path_mirrors
from session_state_schema import load_active_doc, resolve_path
from workflow_paths import seed_profile_pointer_for_tests
from workflow_profile_paths import state_path
from workflow_state_schema import init_compose_session, save_workflow_state

_CYCLE = "feat-g5-retire"
_PROFILE = "lulu-design"
_G5_RESIDUE = (
    "provenance-gate-state.json",
    "provenance-trace-intent.json",
    "provenance-trace-scope.json",
    "provenance-trace-norm.json",
)
_WORKFLOW = Path(__file__).resolve().parents[3]


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _seed_inductive_session(tmp_path: Path) -> Path:
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, _PROFILE)
    active_doc = load_active_doc(resolve_path(_CYCLE, tmp_path, _PROFILE))
    ws = tmp_path / state_path(_CYCLE, active_doc, _PROFILE, tmp_path)
    init_compose_session(ws, mode="tech", cycle_type="feature")
    save_workflow_state(ws, {"current_state": "Working"})
    rev = ws.parent
    save_l_ledger(rev, build_ledger(["L1"]))
    src = tmp_path / "scope-src.md"
    src.write_text("# scope\n", encoding="utf-8")
    package = build_scope_package(
        [{"id": "L1", "title": "L1", "source_path": str(src.resolve())}]
    )
    save_scope_package(rev, package)
    write_source_path_mirrors(rev, package)
    return ws


def _set_state(rev: Path, state: str) -> None:
    ledger = load_l_ledger(rev)
    ledger["by_id"]["L1"]["state"] = state
    save_l_ledger(rev, ledger)


def _g5_gate_payload() -> dict:
    state = init_gate_state(cycle_id=_CYCLE, stage=_PROFILE)
    for gate in ("G2", "G3", "G4"):
        state = close_gate(state, gate)
    state["active_gate"] = "G5"
    return state


def _seed_kept_artifacts(ws: Path, slice_dir: Path) -> None:
    (slice_dir / "_facts.json").write_text("[]\n", encoding="utf-8")
    _write_json(
        opens_path(slice_dir),
        [
            {
                "id": "O-1",
                "status": "open",
                "source": {"actor": "human", "means": "direct"},
                "question": "What stays?",
                "basis": "Open source is not G5 residue",
                "blocking": False,
                "lens": "I",
            }
        ],
    )
    seed_resolved_refs_for_eval(ws, cycle_id=_CYCLE, stage=_PROFILE)


def _seed_g5_residue(slice_dir: Path) -> None:
    for name in _G5_RESIDUE:
        (slice_dir / name).write_text("{}\n", encoding="utf-8")
    _write_json(slice_dir / "inductive-gate-state.json", _g5_gate_payload())


def test_reverse_to_inductive_purges_g5_and_inits_current_schema(tmp_path: Path) -> None:
    ws = _seed_inductive_session(tmp_path)
    rev = ws.parent
    l1 = rev / "L1"
    l1.mkdir(parents=True, exist_ok=True)
    _set_state(rev, "FreeEdit")
    _seed_kept_artifacts(ws, l1)
    _seed_g5_residue(l1)
    (l1 / "_inductive.complete").write_text("ok\n", encoding="utf-8")
    (l1 / "_deductive.complete").write_text("ok\n", encoding="utf-8")
    (l1 / "_writing.complete").write_text("ok\n", encoding="utf-8")

    result = l_step_control.reverse_to_inductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["state"] == "Inductive"
    for name in _G5_RESIDUE:
        assert not (l1 / name).is_file()
    assert not (l1 / "_inductive.complete").is_file()
    assert not (l1 / "_deductive.complete").is_file()
    assert (l1 / "_facts.json").is_file()
    assert opens_path(l1).is_file()
    assert (rev / "resolved-refs.json").is_file()
    assert not (l1 / "evaluate-state.md").is_file()
    gate = load_gate_state(l1 / "inductive-gate-state.json")
    assert gate["active_gate"] == "G2"
    assert gate["gates"]["G2"]["status"] == "active"
    assert "G1" not in gate["gates"]


def test_enter_inductive_restart_replaces_raw_g5_with_current_schema(
    tmp_path: Path,
) -> None:
    ws = _seed_inductive_session(tmp_path)
    rev = ws.parent
    l1 = rev / "L1"
    l1.mkdir(parents=True, exist_ok=True)
    _seed_g5_residue(l1)

    _set_state(rev, "FactIntake")
    (l1 / "_fact_intake.complete").write_text("ok\n", encoding="utf-8")
    result = l_step_control.enter_inductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    for name in _G5_RESIDUE:
        assert not (l1 / name).is_file()
    gate = load_gate_state(l1 / "inductive-gate-state.json")
    assert gate["active_gate"] == "G2"
    assert gate["gates"]["G2"]["status"] == "active"
    assert "G1" not in gate["gates"]


def test_l_execution_defers_eval_admission_to_begin_eval_round() -> None:
    text = (
        Path(__file__).resolve().parents[2] / "references" / "l-execution.md"
    ).read_text(encoding="utf-8")
    evaluating = text.split("## Evaluating", 1)[1].split("## Reopen", 1)[0]
    assert "$EVAL_CONTROL begin-eval-round" in evaluating
    assert "$L_STEP enter-evaluating" not in evaluating.split("Do not run", 1)[0]
    assert "$EVAL_HANDOFF" not in text
    assert "Eval SKILL does not run `$L_STEP`" in evaluating
    assert "$L_STEP accept --confirm" in evaluating
    bind = text.split("## Bind", 1)[1].split("## Spine", 1)[0]
    assert "begin-eval-round" in bind
    assert "do not run it as `$L_STEP`" in bind


def test_complete_inductive_stays_incomplete_on_raw_g5(tmp_path: Path) -> None:
    ws = _seed_inductive_session(tmp_path)
    rev = ws.parent
    l1 = rev / "L1"
    l1.mkdir(parents=True, exist_ok=True)
    _set_state(rev, "Inductive")
    (l1 / "_facts.json").write_text("[]\n", encoding="utf-8")
    _write_json(l1 / "inductive-gate-state.json", _g5_gate_payload())

    result = l_step_control.complete_inductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "inductive_incomplete"
    raw = json.loads((l1 / "inductive-gate-state.json").read_text(encoding="utf-8"))
    assert raw["active_gate"] == "G5"


def test_runtime_surface_has_no_g5_or_support_mixin() -> None:
    compose = _WORKFLOW / "compose"
    assert not (compose / "inductive-runner" / "gates" / "g1-shape.md").exists()
    assert not (compose / "scripts" / "inductive" / "inductive_shape_control.py").exists()
    assert not (compose / "inductive-runner" / "gates" / "g5-provenance.md").exists()
    assert not (compose / "inductive-runner" / "g5-provenance-runner").exists()
    assert not (compose / "scripts" / "inductive" / "provenance_gate_control.py").exists()
    assert not (compose / "scripts" / "inductive" / "provenance_trace_schema.py").exists()
    assert not (compose / "scripts" / "inductive" / "intent_demands.py").exists()
    assert not (compose / "scripts" / "core" / "compose_eval_adapter_support.py").exists()
    assert not (compose / "references" / "provenance-algorithm-semantics.md").exists()
