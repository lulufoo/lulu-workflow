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
from resolved_refs_schema import frozen_delivered_refs  # noqa: E402
from workflow_state_schema import init_drafting, load_workflow_state  # noqa: E402

from init_drafting_helpers import (  # noqa: E402
    seed_provenance_artifacts,
    seed_tech_design_session,
    seed_tech_plan_session,
    tech_design_scope_refs,
)

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


def _write_g5_closed(revision_dir: Path) -> None:
    revision_dir.mkdir(parents=True, exist_ok=True)
    gate_path = revision_dir / "provenance-gate-state.json"
    gate_path.write_text(
        json.dumps({"version": "1", "gate": "G5", "status": "closed"}),
        encoding="utf-8",
    )


def _seed_inductive_progress(tmp_path: Path, *, revision: int = 1) -> Path:
    rev_dir = tmp_path / doc_dir(_CYCLE, revision, _PROFILE_DESIGN, tmp_path)
    progress_schema.save_drafting_progress(
        _progress_path(tmp_path, _PROFILE_DESIGN, revision=revision),
        {"version": "1", "cycle_id": _CYCLE, "current_step": "Inductive"},
        profile_id=_PROFILE_DESIGN,
        project_root=tmp_path,
        cycle_id=_CYCLE,
    )
    return rev_dir


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


def test_inductive_dispatch_carries_provenance_refs_tech(tmp_path: Path) -> None:
    seed_tech_design_session(tmp_path, cycle_id=_CYCLE)

    result = draft_control.begin_inductive(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)

    dispatch = result["dispatch_input"]
    assert "INTENT_BASELINE_REFS: []" in dispatch
    assert "NORM_CONSTRAINT_REFS: []" in dispatch


def test_inductive_dispatch_intent_baseline_from_spec_product(tmp_path: Path) -> None:
    from delivered_refs_schema import DeliveredRef  # noqa: WPS433

    spec_doc = tmp_path / "spec" / "product-doc.md"
    spec_doc.parent.mkdir(parents=True, exist_ok=True)
    spec_doc.write_text("# Spec\n", encoding="utf-8")
    decision = tmp_path / ".cache/cursor/lulu-dev-workflow" / _CYCLE / "lulu-approach" / "decision-doc.md"
    decision.parent.mkdir(parents=True, exist_ok=True)
    decision.write_text("# Decision\n", encoding="utf-8")
    refs = [
        DeliveredRef(type="lulu-approach", path=str(decision.resolve())),
        DeliveredRef(type="lulu-spec", path=str(spec_doc.resolve())),
    ]
    seed_tech_design_session(tmp_path, cycle_id=_CYCLE, mode="product", delivered_refs=refs)

    result = draft_control.begin_inductive(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)

    dispatch = result["dispatch_input"]
    assert "lulu-spec" in dispatch
    assert str(spec_doc.resolve()) in dispatch


def test_inductive_complete_rejects_g4_without_g5(tmp_path: Path) -> None:
    seed_tech_design_session(tmp_path, cycle_id=_CYCLE)
    rev_dir = _seed_inductive_progress(tmp_path)
    _write_g4_closed(rev_dir)

    result = draft_control.inductive_complete(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)

    assert result["ok"] is False
    assert result["reason"] == "inductive Gate 5 not closed"


def test_inductive_complete_succeeds_when_g4_and_g5_closed(tmp_path: Path) -> None:
    seed_tech_design_session(tmp_path, cycle_id=_CYCLE)
    rev_dir = _seed_inductive_progress(tmp_path)
    _write_g4_closed(rev_dir)
    _write_g5_closed(rev_dir)

    result = draft_control.inductive_complete(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)

    assert result["ok"] is True
    assert result["command"] == "inductive-complete"


def test_begin_init_rejects_inductive_step_without_g5(tmp_path: Path) -> None:
    seed_tech_design_session(tmp_path, cycle_id=_CYCLE)
    rev_dir = _seed_inductive_progress(tmp_path)
    _write_g4_closed(rev_dir)

    result = draft_control.begin_init(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)

    assert result["ok"] is False
    assert "inductive Gate 5 not closed" in result["reason"]


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
    rev1_refs = frozen_delivered_refs(rev1_ws.parent)
    rev2_ws = tmp_path / state_path(_CYCLE, 2, _PROFILE_DESIGN, tmp_path)
    init_drafting(rev2_ws, mode=rev1_state["mode"])
    seed_provenance_artifacts(
        rev2_ws,
        cycle_id=_CYCLE,
        project_root=tmp_path,
        stage=_PROFILE_DESIGN,
        mode=rev1_state["mode"],
        scope_refs=tech_design_scope_refs(rev1_refs),
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
