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
        "## 3. Direction Readiness\n\nTBD\n\n## 4. Direction Comparison\n\nTBD\n\n"
        "## 5. Settled Direction\n\n"
        "### Decision Rationale\n\nTBD\n\n"
        "### Scope\n\n"
        "**Applies to:** TBD\n\n"
        "**Explicitly excludes:** TBD\n\n"
        "### Landing Approach\n\nTBD\n\n"
        "## 6. Assumptions & Risks\n\nTBD\n\n"
        "## 7. Execution Analysis\n\n### 7.1 Acceptance Criteria\n\nTBD\n"
    )


@pytest.fixture
def template_config(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / ".cursor" / "lulu-workflow"
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
            {
                "lens": "acceptance_criteria",
                "question": "What intent-level success signal means a direction is right?",
                "answer": "Owner can demo the chosen path end-to-end",
                "na": False,
            },
            {
                "lens": "impact_surface",
                "question": "Who must weigh in before we pick a direction?",
                "answer": "Owning team lead",
                "na": False,
            },
            {
                "lens": "external_dependencies",
                "question": "Any external promise that locks once we choose?",
                "answer": "Vendor SLA assumed stable",
                "na": False,
            },
            {
                "lens": "implementation_sketch",
                "question": "Any irreversible landing preference?",
                "answer": "Prefer reversible feature flag path",
                "na": False,
            },
            {
                "lens": "gap_check",
                "question": "What failure class are we most afraid to miss?",
                "answer": "Silent data loss on rollback",
                "na": False,
            },
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


def test_loop_a_d_x_r_human_decision_stays_active(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
                "exit": "human_decision",
                "assumptions": [
                    {
                        "id": "A1",
                        "risk_level": "H",
                        "risk_class": "decision",
                        "risk_state": "open",
                        "risk_consequence": "Export blocked",
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
    assert gate_state["active_gate"] == "R"
    assert gate_state["gates"]["R"]["status"] == "active"


def test_loop_a_r_dc_exit_advances_to_dc(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert gate_state.get("skipped_gates") == []
