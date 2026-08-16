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


def _seed(tmp_path: Path, *, order: list[str] | None = None) -> Path:
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, _PROFILE)
    active_doc = load_active_doc(resolve_path(_CYCLE, tmp_path, _PROFILE))
    ws = tmp_path / state_path(_CYCLE, active_doc, _PROFILE, tmp_path)
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


def test_enter_producer_deductive(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    result = l_step_control.enter_producer(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["state"] == "Deductive"
    assert "SOURCE_PATH" in result["dispatch_input"]
    assert load_l_ledger(ws.parent)["by_id"]["L1"]["state"] == "Deductive"


def test_enter_producer_requires_pending(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "Writing")
    result = l_step_control.enter_producer(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "illegal_transition"


def test_complete_producer_requires_facts(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "Deductive")
    result = l_step_control.complete_producer(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "producer_incomplete"


def test_complete_producer_writes_stamp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    _set_state(rev, "Deductive")
    (rev / "L1" / "_facts.json").write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(l_step_control, "_opaque_producer_closed", lambda *a, **k: True)
    result = l_step_control.complete_producer(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert (rev / "L1" / "_producer.complete").is_file()


def test_enter_writing_after_producer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    _set_state(rev, "Deductive")
    _stamp(rev, "_producer.complete")
    (rev / "L1" / "_facts.json").write_text("[]\n", encoding="utf-8")
    monkeypatch.setattr(l_step_control, "_opaque_producer_closed", lambda *a, **k: True)
    result = l_step_control.enter_writing(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["state"] == "Writing"


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


def test_writing_cannot_reverse_to_producer(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    _set_state(ws.parent, "Writing")
    result = l_step_control.reverse_to_producer(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "illegal_transition"


def test_reverse_to_producer_resets_stamp(tmp_path: Path) -> None:
    ws = _seed(tmp_path)
    rev = ws.parent
    _set_state(rev, "FreeEdit")
    _stamp(rev, "_producer.complete")
    (rev / "L1" / "_facts.json").write_text("[]\n", encoding="utf-8")
    result = l_step_control.reverse_to_producer(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["state"] == "Deductive"
    assert not (rev / "L1" / "_producer.complete").is_file()
    assert (rev / "L1" / "_facts.json").is_file()


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
        producer_ok=True,
        writing_ok=True,
        freeedit=True,
    ) == ["begin-eval-round", "reverse-to-producer", "reverse-to-writing"]


def test_status_pending_next_actions(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = l_step_control.draft_status(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    assert result["state"] == "Pending"
    assert result["next_actions"] == ["enter-producer"]


def test_frozen_focus_rejected(tmp_path: Path) -> None:
    ws = _seed(tmp_path, order=["L1", "L2"])
    ledger = load_l_ledger(ws.parent)
    ledger["by_id"]["L1"]["state"] = "Completed"
    ledger["by_id"]["L2"]["frozen"] = True
    save_l_ledger(ws.parent, ledger)
    result = l_step_control.enter_producer(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "illegal_transition"
