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

from delivered_refs_schema import DeliveredRef  # noqa: E402
from init_drafting_helpers import (  # noqa: E402
    seed_product_spec_session,
    seed_provenance_artifacts,
    seed_tech_design_session,
    seed_tech_plan_session,
    tech_design_scope_refs,
)
from resolved_refs_schema import resolved_scope_ref, write_resolved_refs  # noqa: E402

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
    (scope_dir / "ST.json").write_text(
        json.dumps(
            {
                "key": "ST",
                "status": "cleared",
                "frontier_kw": 0,
            }
        ),
        encoding="utf-8",
    )


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


def test_begin_deductive_succeeds_for_lulu_plan(tmp_path: Path) -> None:
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, profile_id="lulu-plan")

    result = draft_control.begin_deductive(_CYCLE, tmp_path, profile_id="lulu-plan")

    assert result["ok"] is True
    dispatch = result["dispatch_input"]
    assert "COMPOSE_PROFILE:      lulu-plan" in dispatch
    assert "DEDUCTIVE_OUT_DIR:" in dispatch
    assert "/lulu-plan/revision1" in dispatch
    progress = progress_schema.load_drafting_progress(
        _progress_path(tmp_path, "lulu-plan"),
        profile_id="lulu-plan",
        project_root=tmp_path,
        cycle_id=_CYCLE,
    )
    assert progress["current_step"] == "Deductive"


def test_begin_deductive_rejects_inductive_profile(tmp_path: Path) -> None:
    seed_tech_design_session(tmp_path, cycle_id=_CYCLE)

    result = draft_control.begin_deductive(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)

    assert result["ok"] is False
    assert "begin-inductive" in result["reason"]


def test_begin_init_rejects_plan_without_deductive(tmp_path: Path) -> None:
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, profile_id="lulu-plan")

    result = draft_control.begin_init(_CYCLE, tmp_path, profile_id="lulu-plan")

    assert result["ok"] is False
    assert "Deductive not run" in result["reason"]


def test_begin_init_rejects_open_deductive_pending(tmp_path: Path) -> None:
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, profile_id="lulu-plan")
    rev = tmp_path / doc_dir(_CYCLE, 1, "lulu-plan", tmp_path)
    progress_schema.save_drafting_progress(
        _progress_path(tmp_path, "lulu-plan"),
        {"version": "1", "cycle_id": _CYCLE, "current_step": "Deductive"},
        profile_id="lulu-plan",
        project_root=tmp_path,
        cycle_id=_CYCLE,
    )
    (rev / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-1", "text": "seed", "lens_tags": ["AR"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (rev / "deductive-pending.json").write_text(
        json.dumps(
            {
                "version": 1,
                "items": [
                    {
                        "id": "P-1",
                        "kind": "edge_hole",
                        "status": "open",
                        "lens": "T",
                        "summary": "uncovered SK",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = draft_control.begin_init(_CYCLE, tmp_path, profile_id="lulu-plan")

    assert result["ok"] is False
    assert "open deductive pending" in result["reason"]


def test_begin_init_rejects_missing_deductive_pending_file(tmp_path: Path) -> None:
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, profile_id="lulu-plan")
    rev = tmp_path / doc_dir(_CYCLE, 1, "lulu-plan", tmp_path)
    progress_schema.save_drafting_progress(
        _progress_path(tmp_path, "lulu-plan"),
        {"version": "1", "cycle_id": _CYCLE, "current_step": "Deductive"},
        profile_id="lulu-plan",
        project_root=tmp_path,
        cycle_id=_CYCLE,
    )
    (rev / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-1", "text": "seed", "lens_tags": ["AR"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    # No deductive-pending.json → hard gate must fail (B1).
    result = draft_control.begin_init(_CYCLE, tmp_path, profile_id="lulu-plan")
    assert result["ok"] is False
    assert "deductive-pending.json missing" in result["reason"]


def test_deductive_complete_and_begin_init_when_gate_clear(tmp_path: Path) -> None:
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, profile_id="lulu-plan")
    rev = tmp_path / doc_dir(_CYCLE, 1, "lulu-plan", tmp_path)
    progress_schema.save_drafting_progress(
        _progress_path(tmp_path, "lulu-plan"),
        {"version": "1", "cycle_id": _CYCLE, "current_step": "Deductive"},
        profile_id="lulu-plan",
        project_root=tmp_path,
        cycle_id=_CYCLE,
    )
    (rev / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-1", "text": "seed", "lens_tags": ["AR"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (rev / "deductive-pending.json").write_text(
        json.dumps({"version": 1, "items": []}, ensure_ascii=False),
        encoding="utf-8",
    )

    complete = draft_control.deductive_complete(
        _CYCLE, tmp_path, profile_id="lulu-plan"
    )
    assert complete["ok"] is True

    begin = draft_control.begin_init(_CYCLE, tmp_path, profile_id="lulu-plan")
    assert begin["ok"] is True
    assert "REVISION_DIR:" in begin["dispatch_input"]


def test_begin_inductive_succeeds_for_lulu_spec(tmp_path: Path) -> None:
    seed_product_spec_session(tmp_path, cycle_id=_CYCLE)

    result = draft_control.begin_inductive(_CYCLE, tmp_path, profile_id="lulu-spec")

    assert result["ok"] is True
    dispatch = result["dispatch_input"]
    assert "COMPOSE_PROFILE:      lulu-spec" in dispatch
    assert "INTENT_BASELINE_REFS: []" in dispatch
    assert "lulu-bet" in dispatch or "decision-doc.md" in dispatch


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
    assert "SCOPE_REF:" in dispatch
    assert "DECISION_FACTS_PATH:" not in dispatch


def test_inductive_dispatch_scope_ref_is_decision_fact(tmp_path: Path) -> None:
    from decision_fact_claim_schema import claim_ledger_path, load_claim_ledger  # noqa: E402

    seed_tech_design_session(tmp_path, cycle_id=_CYCLE)
    rev = tmp_path / doc_dir(_CYCLE, 1, _PROFILE_DESIGN, tmp_path)
    fact = tmp_path / "decision-fact.json"
    fact.write_text(
        json.dumps(
            {
                "version": 1,
                "gates": {
                    "D": [{"id": "D-1", "slot": "D.x", "text": "pick A"}],
                },
            }
        ),
        encoding="utf-8",
    )
    write_resolved_refs(
        rev,
        cycle_id=_CYCLE,
        stage=_PROFILE_DESIGN,
        run_mode="tech",
        scope_ref=DeliveredRef(type="lulu-approach", path=str(fact.resolve())),
        intent_baseline_refs=[],
        norm_constraint_refs=[],
    )

    result = draft_control.begin_inductive(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)
    assert result["ok"] is True
    assert f"SCOPE_REF:            {fact.resolve().as_posix()}" in result["dispatch_input"]
    assert "DECISION_FACTS_PATH:" not in result["dispatch_input"]
    ledger = load_claim_ledger(claim_ledger_path(rev))
    assert ledger["mode"] == "units"
    assert "D-1" in ledger["units"]


def test_begin_inductive_surfaces_claim_wipe_refusal(tmp_path: Path) -> None:
    """Units ledger + missing fact → structured failure, not uncaught ValueError."""
    from decision_fact_claim_schema import (  # noqa: E402
        claim_ledger_path,
        ensure_claim_ledger,
    )

    seed_tech_design_session(tmp_path, cycle_id=_CYCLE)
    rev = tmp_path / doc_dir(_CYCLE, 1, _PROFILE_DESIGN, tmp_path)
    fact = tmp_path / "decision-fact.json"
    fact.write_text(
        json.dumps(
            {
                "version": 1,
                "gates": {
                    "D": [{"id": "D-1", "slot": "D.x", "text": "pick A"}],
                },
            }
        ),
        encoding="utf-8",
    )
    write_resolved_refs(
        rev,
        cycle_id=_CYCLE,
        stage=_PROFILE_DESIGN,
        run_mode="tech",
        scope_ref=DeliveredRef(type="lulu-approach", path=str(fact.resolve())),
        intent_baseline_refs=[],
        norm_constraint_refs=[],
    )
    ensure_claim_ledger(rev, decision_fact_path=str(fact.resolve()))
    assert claim_ledger_path(rev).is_file()
    fact.unlink()

    result = draft_control.begin_inductive(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)
    assert result["ok"] is False
    assert "claim ledger" in result["reason"]
    assert "refusing to wipe" in result["reason"]
    # Must not have advanced drafting progress on failure.
    assert not _progress_path(tmp_path, _PROFILE_DESIGN).exists()


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
    assert result["section_files"] == ["ST.json"]


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


def test_begin_init_k2_requires_facts_when_inductive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """K2: inductive Init → missing _facts.json is a hard error."""
    seed_tech_design_session(tmp_path, cycle_id=_CYCLE)
    rev_dir = _seed_inductive_progress(tmp_path)
    _write_g4_closed(rev_dir)
    _write_g5_closed(rev_dir)

    monkeypatch.setattr(
        draft_control,
        "_drafting_config",
        lambda *a, **k: {"inductive": True},
    )

    result = draft_control.begin_init(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)
    assert result["ok"] is False
    assert "_facts.json missing" in result["reason"]
    assert "seed/settle" in result["reason"]


def test_begin_init_k2_passes_when_facts_present(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_tech_design_session(tmp_path, cycle_id=_CYCLE)
    rev_dir = _seed_inductive_progress(tmp_path)
    _write_g4_closed(rev_dir)
    _write_g5_closed(rev_dir)
    (rev_dir / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-1", "text": "projected", "lens_tags": ["ST"], "source": ["ST-d1"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        draft_control,
        "_drafting_config",
        lambda *a, **k: {"inductive": True},
    )

    result = draft_control.begin_init(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)
    assert result["ok"] is True
    assert "REVISION_DIR:" in result["dispatch_input"]
    assert "SCOPE_FACTS_PATH:" in result["dispatch_input"]
    assert "INDUCTIVE_DIR:" not in result["dispatch_input"]
    # Empty when resolved-refs has no facts_ref
    assert "SCOPE_FACTS_PATH:     \n" in result["dispatch_input"] or (
        "SCOPE_FACTS_PATH:     " in result["dispatch_input"]
        and result["dispatch_input"].split("SCOPE_FACTS_PATH:")[1].split("\n")[0].strip()
        == ""
    )


def test_begin_init_dispatch_includes_nonempty_scope_facts_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ws = seed_tech_design_session(tmp_path, cycle_id=_CYCLE)
    rev_dir = _seed_inductive_progress(tmp_path)
    _write_g4_closed(rev_dir)
    _write_g5_closed(rev_dir)
    (rev_dir / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-1", "text": "projected", "lens_tags": ["ST"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    upstream_facts = tmp_path / "upstream" / "_facts.json"
    upstream_facts.parent.mkdir(parents=True, exist_ok=True)
    upstream_facts.write_text("[]\n", encoding="utf-8")
    scope = resolved_scope_ref(ws.parent)
    assert scope is not None
    write_resolved_refs(
        rev_dir,
        cycle_id=_CYCLE,
        stage=_PROFILE_DESIGN,
        run_mode="tech",
        scope_ref=scope,
        intent_baseline_refs=[],
        norm_constraint_refs=[],
        facts_ref=DeliveredRef(
            type="lulu-design",
            path=str(upstream_facts.resolve()),
        ),
    )

    monkeypatch.setattr(
        draft_control,
        "_drafting_config",
        lambda *a, **k: {"inductive": True},
    )

    result = draft_control.begin_init(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)
    assert result["ok"] is True
    assert f"SCOPE_FACTS_PATH:     {upstream_facts.resolve()}" in result["dispatch_input"]


def test_begin_init_real_design_profile_requires_facts(tmp_path: Path) -> None:
    """Lock: real lulu-design inductive profile requires projected _facts.json."""
    profile = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "lulu-design"
            / "compose-profile.json"
        ).read_text(encoding="utf-8")
    )
    assert profile["drafting"]["inductive"] is True
    assert "display_layer" not in profile.get("drafting", {})

    seed_tech_design_session(tmp_path, cycle_id=_CYCLE)
    rev_dir = _seed_inductive_progress(tmp_path)
    _write_g4_closed(rev_dir)
    _write_g5_closed(rev_dir)
    assert not (rev_dir / "_facts.json").exists()

    result = draft_control.begin_init(_CYCLE, tmp_path, profile_id=_PROFILE_DESIGN)
    assert result["ok"] is False
    assert "_facts.json missing" in result["reason"]

