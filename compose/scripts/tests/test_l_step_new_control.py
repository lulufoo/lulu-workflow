#!/usr/bin/env python3
"""Tests for rewritten $L_STEP command surface."""

from __future__ import annotations

import json
from pathlib import Path

import bootstrap  # noqa: F401
import pytest

import l_step_control
from l_ledger_schema import build_ledger, load_l_ledger, save_l_ledger
from scope_package_schema import build_scope_package, save_scope_package, write_source_path_mirrors
from session_state_schema import load_active_doc, resolve_path
from workflow_paths import seed_profile_pointer_for_tests
from workflow_profile_paths import state_path
from workflow_state_schema import init_compose_session, save_workflow_state

_CYCLE = "feat-l-step"
_PROFILE = "lulu-plan"


def _seed(
    tmp_path: Path,
    *,
    order: list[str] | None = None,
    profile: str = _PROFILE,
) -> Path:
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, profile)
    active_doc = load_active_doc(resolve_path(_CYCLE, tmp_path, profile))
    ws = tmp_path / state_path(_CYCLE, active_doc, profile, tmp_path)
    init_compose_session(ws, mode="tech", cycle_type="feature")
    save_workflow_state(ws, {"current_state": "Working"})
    rev = ws.parent
    ids = order or ["L1"]
    save_l_ledger(rev, build_ledger(ids))
    src = tmp_path / "scope-src.md"
    src.write_text("# scope\n", encoding="utf-8")
    slices = [
        {"id": nid, "title": nid, "source_path": str(src.resolve())}
        for nid in ids
    ]
    package = build_scope_package(slices)
    save_scope_package(rev, package)
    write_source_path_mirrors(rev, package)
    return ws


def _stamp(rev: Path, name: str, nid: str = "L1") -> None:
    path = rev / nid / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ok\n", encoding="utf-8")


def _set_state(rev: Path, state: str, nid: str = "L1") -> None:
    ledger = load_l_ledger(rev)
    ledger["by_id"][nid]["state"] = state
    save_l_ledger(rev, ledger)


def _ready_fact_intake(rev: Path, nid: str = "L1") -> None:
    _set_state(rev, "FactIntake", nid)
    _stamp(rev, "_fact_intake.complete", nid)


def test_enter_fact_intake_from_pending(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    result = l_step_control.enter_fact_intake(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["state"] == "FactIntake"
    assert "SOURCE_PATH" in result["dispatch_input"]
    assert "REQUIRE_SEED_ORIGIN:  false" in result["dispatch_input"]
    assert load_l_ledger(ws.parent)["by_id"]["L1"]["state"] == "FactIntake"


def test_enter_deductive_from_fact_intake(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _ready_fact_intake(ws.parent)
    result = l_step_control.enter_deductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["state"] == "Deductive"
    assert "SOURCE_PATH" in result["dispatch_input"]
    assert load_l_ledger(ws.parent)["by_id"]["L1"]["state"] == "Deductive"


def test_enter_deductive_requires_fact_intake(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    result = l_step_control.enter_deductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "illegal_transition"


def test_enter_deductive_rejects_other_state(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "Writing")
    result = l_step_control.enter_deductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "illegal_transition"


def test_enter_inductive_rejected_on_plan(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _ready_fact_intake(ws.parent)
    result = l_step_control.enter_inductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "illegal_transition"


def test_complete_fact_intake_requires_facts(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "FactIntake")
    result = l_step_control.complete_fact_intake(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "fact_intake_incomplete"


def test_complete_fact_intake_writes_stamp(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    _set_state(rev, "FactIntake")
    (rev / "L1").mkdir(parents=True, exist_ok=True)
    (rev / "L1" / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-1", "text": "seed fact", "lens_tags": []}],
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    result = l_step_control.complete_fact_intake(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert (rev / "L1" / "_fact_intake.complete").is_file()


def test_status_fact_intake_next_actions(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "FactIntake")
    result = l_step_control.draft_status(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["next_actions"] == ["run-fact-intake"]
    _stamp(ws.parent, "_fact_intake.complete")
    result = l_step_control.draft_status(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["next_actions"] == ["enter-deductive"]


def test_complete_deductive_requires_facts(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "Deductive")
    result = l_step_control.complete_deductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "deductive_incomplete"


def test_complete_deductive_writes_stamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    _set_state(rev, "Deductive")
    (rev / "L1" / "_facts.json").write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(l_step_control, "_opaque_deductive_closed", lambda *a, **k: True)
    result = l_step_control.complete_deductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert (rev / "L1" / "_deductive.complete").is_file()


def test_enter_writing_after_deductive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    _set_state(rev, "Deductive")
    _stamp(rev, "_deductive.complete")
    (rev / "L1" / "_facts.json").write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(l_step_control, "_opaque_deductive_closed", lambda *a, **k: True)
    result = l_step_control.enter_writing(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["state"] == "Writing"


def test_enter_writing_rejects_inductive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    _set_state(rev, "Inductive")
    _stamp(rev, "_inductive.complete")
    (rev / "L1" / "_facts.json").write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(l_step_control, "_opaque_deductive_closed", lambda *a, **k: True)
    result = l_step_control.enter_writing(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "illegal_transition"


def test_enter_freeedit_requires_writing_stamp(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "Writing")
    result = l_step_control.enter_freeedit(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "writing_incomplete"


def test_enter_freeedit_success(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "Writing")
    _stamp(ws.parent, "_writing.complete")
    result = l_step_control.enter_freeedit(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["state"] == "FreeEdit"


def test_writing_cannot_reverse_to_deductive(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "Writing")
    result = l_step_control.reverse_to_deductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "illegal_transition"


def test_reverse_to_deductive_resets_stamp(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    _set_state(rev, "FreeEdit")
    _stamp(rev, "_deductive.complete")
    _stamp(rev, "_fact_intake.complete")
    (rev / "L1" / "_facts.json").write_text(
        json.dumps(
            [
                {"id": "F-1", "text": "seed", "lens_tags": [], "origin": {"type": "seed", "ref": ["doc"]}},
                {"id": "F-2", "text": "old", "lens_tags": ["CTX"], "origin": {"type": "derived", "ref": ["F-1"]}},
            ],
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    result = l_step_control.reverse_to_deductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["state"] == "Deductive"
    assert not (rev / "L1" / "_deductive.complete").is_file()
    assert (rev / "L1" / "_fact_intake.complete").is_file()
    facts = json.loads((rev / "L1" / "_facts.json").read_text(encoding="utf-8"))
    assert [f["id"] for f in facts] == ["F-1"]


def test_reverse_to_inductive_rejected_on_plan(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "FreeEdit")
    result = l_step_control.reverse_to_inductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "illegal_transition"


def test_accept_requires_confirm(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = l_step_control.accept_l(_CYCLE, tmp_path, profile_id=_PROFILE, confirm=False)
    assert result["code"] == "confirmation_required"


def test_accept_sets_completed_without_changing_focus(tmp_path: Path) -> None:
    ws = _seed(tmp_path, order=["L1", "L2"])
    rev = ws.parent
    _set_state(rev, "Evaluating")
    l_step_control._write_eval_run(rev / "L1", load_l_ledger(rev))
    result = l_step_control.accept_l(_CYCLE, tmp_path, profile_id=_PROFILE, confirm=True)
    assert result["ok"] is True, result
    ledger = load_l_ledger(rev)
    assert ledger["by_id"]["L1"]["state"] == "Completed"
    assert ledger["focus"] == "L1"


def test_fix_to_freeedit(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    _set_state(rev, "Evaluating")
    l_step_control._write_eval_run(rev / "L1", load_l_ledger(rev))
    result = l_step_control.fix_l(_CYCLE, tmp_path, profile_id=_PROFILE, confirm=True)
    assert result["ok"] is True, result
    assert load_l_ledger(rev)["by_id"]["L1"]["state"] == "FreeEdit"


def test_re_evaluate_new_run_id(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    _set_state(rev, "Evaluating")
    first = l_step_control._write_eval_run(rev / "L1", load_l_ledger(rev))
    result = l_step_control.re_evaluate(_CYCLE, tmp_path, profile_id=_PROFILE, confirm=True)
    assert result["ok"] is True, result
    assert result["state"] == "Evaluating"
    assert result["eval_run_id"] != first


def test_reopen_completed_to_freeedit(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "Completed")
    result = l_step_control.reopen_current(
        _CYCLE, tmp_path, profile_id=_PROFILE, confirm=True
    )
    assert result["ok"] is True, result
    assert result["state"] == "FreeEdit"


def test_enter_evaluating_from_freeedit_after_backtrack_shape(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "FreeEdit")
    _stamp(ws.parent, "_writing.complete")
    result = l_step_control.enter_evaluating(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["state"] == "Evaluating"
    assert result["eval_run_id"]


def test_rollback_evaluating_restores_writing_and_clears_eval_run(
    tmp_path: Path,
) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    ledger = load_l_ledger(rev)
    ledger["by_id"]["L1"]["state"] = "Evaluating"
    save_l_ledger(rev, ledger)
    slice_dir = rev / "L1"
    slice_dir.mkdir(parents=True, exist_ok=True)
    (slice_dir / "_eval_run.json").write_text("{}\n", encoding="utf-8")
    staging = slice_dir / ".eval-staging" / "lease-1"
    staging.mkdir(parents=True)
    (staging / "x").write_text("tmp", encoding="utf-8")
    l_step_control.rollback_evaluating_phase(
        rev,
        focus="L1",
        previous_phase="Writing",
    )
    assert load_l_ledger(rev)["by_id"]["L1"]["state"] == "Writing"
    assert not (slice_dir / "_eval_run.json").is_file()
    assert not (slice_dir / ".eval-staging").exists()


def test_rollback_evaluating_noop_when_previous_is_not_producer(
    tmp_path: Path,
) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    ledger = load_l_ledger(rev)
    ledger["by_id"]["L1"]["state"] = "Evaluating"
    save_l_ledger(rev, ledger)
    slice_dir = rev / "L1"
    slice_dir.mkdir(parents=True, exist_ok=True)
    (slice_dir / "_eval_run.json").write_text("{}\n", encoding="utf-8")
    staging = slice_dir / ".eval-staging" / "lease-1"
    staging.mkdir(parents=True)
    (staging / "x").write_text("tmp", encoding="utf-8")
    l_step_control.rollback_evaluating_phase(
        rev,
        focus="L1",
        previous_phase="Evaluating",
    )
    assert load_l_ledger(rev)["by_id"]["L1"]["state"] == "Evaluating"
    assert (slice_dir / "_eval_run.json").is_file()
    assert staging.is_dir()


def test_writing_and_freeedit_next_actions_route_to_begin_eval_round() -> None:
    assert l_step_control.derive_step_next_actions(
        "Writing",
        producer_ok=True,
        writing_ok=True,
        freeedit=False,
    ) == ["begin-eval-round"]
    assert l_step_control.derive_step_next_actions(
        "Writing",
        producer_ok=True,
        writing_ok=True,
        freeedit=True,
    ) == ["enter-freeedit", "begin-eval-round"]
    assert l_step_control.derive_step_next_actions(
        "FreeEdit",
        writing_ok=True,
        freeedit=True,
    ) == ["begin-eval-round", "reverse-to-deductive", "reverse-to-writing"]
    assert l_step_control.derive_step_next_actions(
        "FreeEdit",
        writing_ok=True,
        freeedit=True,
        inductive=True,
    ) == [
        "begin-eval-round",
        "reverse-to-inductive",
        "reverse-to-deductive",
        "reverse-to-writing",
    ]


_MIXED_FACTS = [
    {"id": "F-1", "text": "seed", "lens_tags": [], "origin": {"type": "seed", "ref": ["doc"]}},
    {"id": "F-2", "text": "old", "lens_tags": ["CTX"], "origin": {"type": "derived", "ref": ["F-1"]}},
]


def _write_mixed_facts(rev: Path, nid: str = "L1") -> None:
    path = rev / nid / "_facts.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_MIXED_FACTS, ensure_ascii=False) + "\n", encoding="utf-8")


def test_enter_deductive_strips_derived(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    _ready_fact_intake(rev)
    _write_mixed_facts(rev)
    result = l_step_control.enter_deductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    facts = json.loads((rev / "L1" / "_facts.json").read_text(encoding="utf-8"))
    assert [f["id"] for f in facts] == ["F-1"]


def test_serial_design_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    profile = "lulu-design"
    ws = _seed(tmp_path, profile=profile)
    rev = ws.parent
    _ready_fact_intake(rev)
    _write_mixed_facts(rev)
    entered = l_step_control.enter_inductive(_CYCLE, tmp_path, profile_id=profile)
    assert entered["ok"] is True, entered
    assert entered["state"] == "Inductive"
    facts = json.loads((rev / "L1" / "_facts.json").read_text(encoding="utf-8"))
    assert [f["id"] for f in facts] == ["F-1"]
    monkeypatch.setattr(l_step_control, "_opaque_inductive_closed", lambda *a, **k: True)
    complete = l_step_control.complete_inductive(_CYCLE, tmp_path, profile_id=profile)
    assert complete["ok"] is True, complete
    status = l_step_control.draft_status(_CYCLE, tmp_path, profile_id=profile)
    assert status["next_actions"] == ["enter-deductive"]
    deductive = l_step_control.enter_deductive(_CYCLE, tmp_path, profile_id=profile)
    assert deductive["ok"] is True, deductive
    assert deductive["state"] == "Deductive"
    monkeypatch.setattr(l_step_control, "_opaque_deductive_closed", lambda *a, **k: True)
    (rev / "L1" / "_facts.json").write_text("[]\n", encoding="utf-8")
    done = l_step_control.complete_deductive(_CYCLE, tmp_path, profile_id=profile)
    assert done["ok"] is True, done
    writing = l_step_control.enter_writing(_CYCLE, tmp_path, profile_id=profile)
    assert writing["ok"] is True, writing
    assert writing["state"] == "Writing"


def test_status_omits_retired_producer_commands(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = l_step_control.draft_status(_CYCLE, tmp_path, profile_id=_PROFILE)
    retired = {"enter-producer", "complete-producer", "reverse-to-producer"}
    assert retired.isdisjoint(result["next_actions"])
    assert "reverse-to-inductive" not in result["next_actions"]


def test_status_pending_next_actions(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = l_step_control.draft_status(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["state"] == "Pending"
    assert result["next_actions"] == ["enter-fact-intake"]


def test_frozen_focus_rejected(tmp_path: Path) -> None:
    ws = _seed(tmp_path, order=["L1", "L2"])
    ledger = load_l_ledger(ws.parent)
    ledger["by_id"]["L1"]["state"] = "Completed"
    ledger["by_id"]["L2"]["frozen"] = True
    save_l_ledger(ws.parent, ledger)
    result = l_step_control.enter_deductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "illegal_transition"
