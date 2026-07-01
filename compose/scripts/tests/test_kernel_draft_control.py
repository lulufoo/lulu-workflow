#!/usr/bin/env python3
"""Tests for generic compose drafting control."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import bootstrap  # noqa: F401
import draft_control  # noqa: E402
import drafting_progress_schema as progress_schema  # noqa: E402
from session_state_schema import save_active_doc  # noqa: E402
from workflow_profile_paths import doc_dir, inductive_out_dir, session_state_path, state_path  # noqa: E402
from delivered_refs_schema import parse_delivered_refs, parse_scope_refs  # noqa: E402
from workflow_state_schema import init_drafting, load_workflow_state  # noqa: E402

from init_drafting_helpers import seed_tech_design_session, seed_tech_plan_session  # noqa: E402

_CYCLE = "feature-draft-generic"
_PROFILE_DESIGN = "lulu-design"


def _progress_path(project_root: Path, profile_id: str, *, revision: int = 1) -> Path:
    return project_root / doc_dir(_CYCLE, revision, profile_id, project_root) / "drafting-progress.md"


def _write_g4_closed(revision_dir: Path) -> None:
    revision_dir.mkdir(parents=True, exist_ok=True)
    gate_path = revision_dir / "inductive-gate-state.json"
    gate_path.write_text(
        json.dumps({"gates": {"G4": {"status": "closed"}}}),
        encoding="utf-8",
    )
    scope_dir = revision_dir / "inductive-scope"
    scope_dir.mkdir(parents=True, exist_ok=True)
    (scope_dir / "ST.md").write_text("# ST\n", encoding="utf-8")


def test_begin_inductive_rejects_non_inductive_profile(tmp_path: Path) -> None:
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, profile_id="lulu-plan")

    result = draft_control.begin_inductive(_CYCLE, tmp_path, profile_id="lulu-plan")

    assert result["ok"] is False
    assert "drafting.inductive is false" in result["reason"]


def test_begin_inductive_out_dir_under_revision(tmp_path: Path) -> None:
    seed_tech_design_session(tmp_path, cycle_id=_CYCLE)

    result = draft_control.begin_inductive(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)

    assert result["ok"] is True
    dispatch = result["dispatch_input"]
    assert "INDUCTIVE_OUT_DIR:" in dispatch
    assert dispatch.strip().endswith("revision1")
    expected = (tmp_path / inductive_out_dir(_CYCLE, _PROFILE_DESIGN, tmp_path)).as_posix()
    assert f"INDUCTIVE_OUT_DIR:    {expected}" in dispatch


def test_revision2_inductive_isolated_from_revision1(tmp_path: Path) -> None:
    seed_tech_design_session(tmp_path, cycle_id=_CYCLE)
    rev1 = tmp_path / doc_dir(_CYCLE, 1, _PROFILE_DESIGN, tmp_path)
    _write_g4_closed(rev1)
    progress_schema.save_drafting_progress(
        _progress_path(tmp_path, _PROFILE_DESIGN, revision=1),
        {"version": "1", "cycle_id": _CYCLE, "current_step": "Inductive"},
        profile_id=_PROFILE_DESIGN,
        project_root=tmp_path,
        cycle_id=_CYCLE,
    )

    ss_path = tmp_path / session_state_path(_CYCLE, _PROFILE_DESIGN, tmp_path)
    save_active_doc(ss_path, 2)
    rev1_ws = tmp_path / state_path(_CYCLE, 1, _PROFILE_DESIGN, tmp_path)
    rev1_state = load_workflow_state(rev1_ws)
    rev2_ws = tmp_path / state_path(_CYCLE, 2, _PROFILE_DESIGN, tmp_path)
    init_drafting(
        rev2_ws,
        mode=rev1_state["mode"],
        delivered_refs=parse_delivered_refs(rev1_state),
        scope_refs=parse_scope_refs(rev1_state),
    )

    begin_init = draft_control.begin_init(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)
    assert begin_init["ok"] is False
    assert "Inductive not run" in begin_init["reason"]

    begin_inductive = draft_control.begin_inductive(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)
    assert begin_inductive["ok"] is True
    assert begin_inductive["dispatch_input"].strip().endswith("revision2")


def test_advance_to_freeedit_rejects_profile_without_freeedit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, profile_id="lulu-spec")
    progress_schema.save_drafting_progress(
        _progress_path(tmp_path, "lulu-spec"),
        {"version": "1", "cycle_id": _CYCLE, "current_step": "Initialized"},
        profile_id="lulu-spec",
    )
    monkeypatch.setattr(
        draft_control,
        "load_profile",
        lambda *args, **kwargs: {"drafting": {"freeedit": False}},
    )

    result = draft_control.advance_to_freeedit(_CYCLE, tmp_path, profile_id="lulu-spec")

    assert result["ok"] is False
    assert "drafting.freeedit is false" in result["reason"]


def test_advance_to_freeedit_accepts_legacy_ready(tmp_path: Path) -> None:
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, profile_id="lulu-plan")
    _progress_path(tmp_path, "lulu-plan").write_text(
        "---\nversion: 1\ncycle_id: feature-draft-generic\ncurrent_step: Ready\n---\n",
        encoding="utf-8",
    )

    result = draft_control.advance_to_freeedit(_CYCLE, tmp_path, profile_id="lulu-plan")

    assert result["ok"] is True
    assert result["current_step"] == "FreeEdit"
