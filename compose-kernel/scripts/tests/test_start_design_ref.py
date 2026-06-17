#!/usr/bin/env python3
"""Tests for delivered_refs snapshot in workflow-state and draft dispatch."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bootstrap  # noqa: F401

from delivered_refs_schema import DeliveredRef, parse_delivered_refs
from init_drafting_helpers import (  # noqa: E402
    product_delivered_refs,
    seed_delivered_refs_file,
    seed_tech_plan_session,
    tech_diagnostic_refs,
)
from workflow_state_schema import init_drafting, load_workflow_state  # noqa: E402

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_SHELL_SCRIPTS = _WORKFLOW_ROOT / "tech-plan" / "scripts"
_DRAFTING_SCRIPTS = _SHELL_SCRIPTS / "drafting"
_CYCLE = "feat-design-ref"


def test_init_drafting_stores_delivered_refs(tmp_path: Path):
    path = tmp_path / "workflow-state.md"
    design_path = tmp_path / "design-doc.md"
    design_path.write_text("# Design\n", encoding="utf-8")
    refs = [
        DeliveredRef(type="tech-diagnostic", path="/abs/decision.md"),
        DeliveredRef(type="tech-design", path=str(design_path)),
    ]
    init_drafting(path, mode="tech", delivered_refs=refs)
    loaded = parse_delivered_refs(load_workflow_state(path))
    assert len(loaded) == 2
    assert loaded[1].path == str(design_path)


def test_begin_init_includes_design_doc_path(tmp_path: Path, monkeypatch):
    design_path = tmp_path / "design-doc.md"
    design_path.write_text("# Design\n", encoding="utf-8")
    decision = tmp_path / "decision-doc.md"
    decision.write_text("# Decision\n", encoding="utf-8")
    refs = [
        DeliveredRef(type="tech-diagnostic", path=str(decision.resolve())),
        DeliveredRef(type="tech-design", path=str(design_path.resolve())),
    ]
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, delivered_refs=refs)
    monkeypatch.chdir(tmp_path)
    if str(_SHELL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SHELL_SCRIPTS))
    if str(_DRAFTING_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_DRAFTING_SCRIPTS))
    from draft_control_test_loader import load_draft_control  # noqa: E402

    begin_init = load_draft_control(_DRAFTING_SCRIPTS, module_name="tech_plan_draft_control").begin_init
    result = begin_init(_CYCLE, tmp_path)
    assert result["ok"] is True
    assert "DESIGN_DOC_PATH" in result["dispatch_input"]
    assert str(design_path) in result["dispatch_input"]


def test_begin_init_omits_design_doc_path_when_absent(tmp_path: Path, monkeypatch):
    decision = tmp_path / "decision-doc.md"
    decision.write_text("# Decision\n", encoding="utf-8")
    refs = [DeliveredRef(type="tech-diagnostic", path=str(decision.resolve()))]
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, delivered_refs=refs)
    monkeypatch.chdir(tmp_path)
    if str(_SHELL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SHELL_SCRIPTS))
    if str(_DRAFTING_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_DRAFTING_SCRIPTS))
    from draft_control_test_loader import load_draft_control  # noqa: E402

    begin_init = load_draft_control(_DRAFTING_SCRIPTS, module_name="tech_plan_draft_control").begin_init
    result = begin_init(_CYCLE, tmp_path)
    assert result["ok"] is True
    assert "DESIGN_DOC_PATH" not in result["dispatch_input"]
