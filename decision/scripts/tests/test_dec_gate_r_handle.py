#!/usr/bin/env python3
"""Tests for decision R handle + DC delivery (RR retired)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_gate_control import (  # noqa: E402
    cmd_apply_r_assumptions,
    cmd_check_delivery_ready,
    cmd_complete,
    cmd_complete_assumption,
    cmd_deliver,
    cmd_gate_close,
    cmd_init_session,
)
from dec_register_control import cmd_register_append  # noqa: E402
from dec_workflow_common import gate_state_path, session_state_path  # noqa: E402
from dec_test_helpers import load_rendered_doc, render_session_doc  # noqa: E402
from test_dec_gate_loop_a import _close_qe, _full_template  # noqa: E402

_H_TERMS = (
    "Method: integration test / Owner: QA / Timing: pre-release / "
    "Release condition: export succeeds for 10k rows"
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


def _reach_r_with_open(
    project_root: Path,
    cycle_id: str,
    stage: str,
    *,
    risk_level: str = "H",
    risk_class: str = "decision",
    risk_state: str = "open",
    risk_consequence: str = "Export blocked",
    text: str = "API supports bulk export",
) -> None:
    """Land risk fields via apply-r-assumptions (design primary path)."""
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
    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="assumption",
        payload={"text": text},
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
        cmd_apply_r_assumptions(
            project_root,
            cycle_id,
            stage,
            payload={
                "assumptions": [
                    {
                        "id": "A1",
                        "risk_level": risk_level,
                        "risk_class": risk_class,
                        "risk_state": risk_state,
                        "risk_consequence": risk_consequence,
                    },
                ]
            },
        )
        == 0
    )


def test_r_handle_complete_assumption_dc_deliver(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-r-handle-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _reach_r_with_open(project_root, cycle_id, stage)

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "R"

    assert (
        cmd_complete_assumption(
            project_root,
            cycle_id,
            stage,
            entry_id="A1",
            release_terms=_H_TERMS,
        )
        == 0
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

    doc = load_rendered_doc(project_root, cycle_id, stage)
    assert "integration test" in doc

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "DC"

    ready = cmd_check_delivery_ready(project_root, cycle_id, stage)
    assert ready == 0

    render_session_doc(project_root, cycle_id, stage)

    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "DC",
            {"user_confirmed": True},
        )
        == 0
    )

    assert cmd_deliver(project_root, cycle_id, stage) == 0

    ss = (project_root / session_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    assert "current_state: Completed" in ss


def test_r_dc_low_risk_accepted(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-r-handle-002"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _reach_r_with_open(
        project_root,
        cycle_id,
        stage,
        risk_level="L",
        risk_consequence="Minor UX gap",
        text="Low-risk assumption",
    )

    assert (
        cmd_complete_assumption(
            project_root,
            cycle_id,
            stage,
            entry_id="A1",
            release_terms="Accepted",
        )
        == 0
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


def test_r_exit_dc_forbids_open_risk_state(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-r-handle-open"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _reach_r_with_open(project_root, cycle_id, stage)
    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "R",
            {"exit": "dc", "assumptions": []},
        )
        != 0
    )


def test_r_dc_allows_implementation_class(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-r-handle-impl"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _reach_r_with_open(
        project_root,
        cycle_id,
        stage,
        risk_class="implementation",
        risk_consequence="May overturn later",
        text="Post-impl behavior",
    )
    assert (
        cmd_complete_assumption(
            project_root,
            cycle_id,
            stage,
            entry_id="A1",
            release_terms="Accepted",
        )
        == 0
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

    from dec_register_schema import load_registers  # noqa: WPS433
    from dec_workflow_common import registers_path  # noqa: E402

    registers = load_registers(
        project_root / registers_path(cycle_id, stage),
        r_gate_closed=True,
        r_risk_fields_allowed=True,
    )
    assert registers["assumptions"][0]["risk_state"] == "completed"
    assert registers["assumptions"][0]["release_terms"] == "Accepted"

    doc = load_rendered_doc(project_root, cycle_id, stage)
    assert "implementation" in doc
    assert "Accepted" in doc
