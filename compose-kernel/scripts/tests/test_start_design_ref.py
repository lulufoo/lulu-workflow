#!/usr/bin/env python3
"""Tests for start.py --design-ref."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bootstrap  # noqa: F401

from init_drafting_helpers import seed_tech_plan_session  # noqa: E402
from workflow_state_schema import init_drafting, load_workflow_state  # noqa: E402

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_SHELL_SCRIPTS = _WORKFLOW_ROOT / "tech-plan" / "scripts"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")
_CYCLE = "feat-design-ref"


def test_init_drafting_stores_design_ref(tmp_path: Path):
    path = tmp_path / "workflow-state.md"
    design_path = tmp_path / "design-doc.md"
    design_path.write_text("# Design\n", encoding="utf-8")
    init_drafting(path, mode="tech", design_ref=str(design_path))
    assert load_workflow_state(path)["design_ref"] == str(design_path)


def test_begin_init_includes_design_doc_path(tmp_path: Path, monkeypatch):
    design_path = tmp_path / "design-doc.md"
    design_path.write_text("# Design\n", encoding="utf-8")
    seed_tech_plan_session(
        tmp_path,
        cycle_id=_CYCLE,
        design_ref=str(design_path),
    )
    monkeypatch.chdir(tmp_path)
    if str(_SHELL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SHELL_SCRIPTS))
    from draft_control import begin_init  # noqa: WPS433

    result = begin_init(_CYCLE, tmp_path)
    assert result["ok"] is True
    assert "DESIGN_DOC_PATH" in result["dispatch_input"]
    assert str(design_path) in result["dispatch_input"]


def test_begin_init_omits_design_doc_path_when_empty(tmp_path: Path, monkeypatch):
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, design_ref="")
    monkeypatch.chdir(tmp_path)
    if str(_SHELL_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SHELL_SCRIPTS))
    from draft_control import begin_init  # noqa: WPS433

    result = begin_init(_CYCLE, tmp_path)
    assert result["ok"] is True
    assert "DESIGN_DOC_PATH" not in result["dispatch_input"]
