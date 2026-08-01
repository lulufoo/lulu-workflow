#!/usr/bin/env python3
"""Tests for decision Loop A gates (D / X / R)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_gate_control import (  # noqa: E402
    cmd_gate_close,
    cmd_init_session,
)
from dec_register_control import cmd_register_append  # noqa: E402
from dec_workflow_common import gate_state_path  # noqa: E402
from dec_test_helpers import load_rendered_doc  # noqa: E402


def _full_template() -> str:
    return (
        "# Decision: {title}\n\n"
        "## 1. User Prior\n\n- placeholder\n\n"
        "## 2. Problem Definition\n\nTBD\n\n"
        "## 3. Direction Comparison\n\nTBD\n\n"
        "## 4. Decision Rationale\n\nTBD\n\n"
        "## 5. Scope\n\nTBD\n\n"
        "## 6. Assumptions & Risks\n\nTBD\n\n"
        "## 7. Execution Analysis\n\n### 7.1 Acceptance Criteria\n\nTBD\n"
    )


@pytest.fixture
def template_config(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / "skill-config" / "lulu-dev-workflow"
    cfg_dir.mkdir(parents=True)
    local_template = tmp_path / "decision-doc.template.md"
    local_template.write_text(_full_template(), encoding="utf-8")
    cfg_path = cfg_dir / "workflow-config.json"
    cfg_path.write_text(
        json.dumps({"decision": {"decision_doc_template_url": local_template.as_uri()}}),
        encoding="utf-8",
    )
    return tmp_path


def _close_o(project_root: Path, cycle_id: str, stage: str) -> None:
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "O",
        {"user_confirmed": True},
    )


def _gl_payload() -> dict:
    return {
        "exchanges": [
            {"topic": "T1", "question": "Who confirms go-live?", "answer": "Owner A", "na": False},
            {"topic": "T2", "question": "Human vs machine?", "answer": "Human approves", "na": False},
            {"topic": "T3", "question": "Risk narrative?", "answer": "Latency is risk", "na": False},
            {"topic": "T4", "question": "Ops preference?", "answer": "Business hours only", "na": False},
        ],
        "user_confirmed": True,
    }


def _close_gl(project_root: Path, cycle_id: str, stage: str) -> None:
    cmd_gate_close(project_root, cycle_id, stage, "GL", _gl_payload())


def _close_qe(project_root: Path, cycle_id: str, stage: str) -> None:
    """Close O → Q → GL → E (name kept for call-site compatibility)."""
    _close_o(project_root, cycle_id, stage)
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "Q",
        {"problem_statement": "problem", "constraints": "none"},
    )
    _close_gl(project_root, cycle_id, stage)
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "E",
        {
            "directions": [
                {"name": "A", "approach": "a", "pros": "p", "cons": "c", "recommended": True},
                {"name": "B", "approach": "b", "pros": "p", "cons": "c"},
            ],
            "excluded": [],
            "user_choice": "A",
        },
    )


def test_loop_a_d_x_r_loop_b_exit(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-loop-a-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    assert cmd_init_session(project_root, cycle_id, stage) == 0
    _close_qe(project_root, cycle_id, stage)

    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "D",
            {
                "decision_rationale": "Chose A for stability",
                "applies_to": "export feature",
                "excludes": "mobile client",
                "execution_approach": "backend first",
            },
        )
        == 0
    )

    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="assumption",
        payload={"text": "SSO supports bulk API"},
    )

    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "X",
            {
                "acceptance_criteria": "Users can export CSV in one click",
                "gap": "None",
                "impact_surface": [
                    {"layer": "API", "area": "export", "change_type": "add", "notes": ""},
                ],
                "external_dependencies": [],
                "key_changes": "Add export endpoint",
                "critical_constraints": "Rate limit",
                "reversibility": "easy",
            },
        )
        == 0
    )

    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "R",
            {
                "exit": "loop_b",
                "assumptions": [
                    {
                        "id": "A1",
                        "risk": "H",
                        "risk_class": "decision",
                        "consequence": "Export blocked",
                    },
                ],
            },
        )
        == 0
    )

    doc = load_rendered_doc(project_root, cycle_id, stage)
    assert "Chose A for stability" in doc
    assert "Add export endpoint" in doc
    assert "SSO supports bulk API" in doc

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "V"
    assert gate_state["gates"]["R"]["status"] == "closed"
    assert gate_state["skipped_gates"] == []


def test_loop_a_r_dc_exit_skips_loop_b(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-loop-a-002"
    stage = "decision"
    monkeypatch.chdir(project_root)

    cmd_init_session(project_root, cycle_id, stage)
    _close_qe(project_root, cycle_id, stage)
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "D",
        {
            "decision_rationale": "rationale",
            "applies_to": "scope",
            "excludes": "none",
            "execution_approach": "serial",
        },
    )
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "X",
        {
            "acceptance_criteria": "done",
            "gap": "None",
            "impact_surface": [],
            "external_dependencies": [],
            "key_changes": "k",
            "critical_constraints": "c",
            "reversibility": "easy",
        },
    )

    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "R",
            {"exit": "dc", "assumptions": []},
        )
        == 0
    )

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "DC"
    assert gate_state["skipped_gates"] == ["V", "RR"]
