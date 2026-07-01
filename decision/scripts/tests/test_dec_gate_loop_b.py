#!/usr/bin/env python3
"""Tests for decision Loop B gates (V / RR / DC) and delivery."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_gate_control import (  # noqa: E402
    cmd_check_delivery_ready,
    cmd_deliver,
    cmd_gate_close,
    cmd_init_session,
)
from dec_register_control import cmd_register_append  # noqa: E402
from dec_workflow_common import gate_state_path, session_state_path  # noqa: E402
from dec_test_helpers import load_rendered_doc, render_session_doc  # noqa: E402
from test_dec_gate_loop_a import _close_qe, _full_template  # noqa: E402


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


def _close_through_r_loop_b(project_root: Path, cycle_id: str, stage: str) -> None:
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
        payload={"text": "API supports bulk export"},
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
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "R",
        {
            "exit": "loop_b",
            "assumptions": [
                {"id": "A1", "risk": "H", "consequence": "Export blocked"},
            ],
        },
    )


def test_loop_b_v_rr_dc_deliver(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-loop-b-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_loop_b(project_root, cycle_id, stage)

    h_verification = (
        "Method: integration test / Owner: QA / Timing: pre-release / "
        "Release condition: export succeeds for 10k rows"
    )
    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "V",
            {
                "exit": "rr",
                "assumptions": [
                    {"id": "A1", "risk": "H", "verification": h_verification},
                ],
            },
        )
        == 0
    )

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "RR"

    doc = load_rendered_doc(project_root, cycle_id, stage)
    assert "integration test" in doc

    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "RR",
            {
                "exit": "dc",
                "assumptions": [{"id": "A1", "released": True}],
            },
        )
        == 0
    )

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
    assert "current_state: Delivered" in ss

    from cycle_delivered_refs import load_delivered_refs_file  # noqa: WPS433

    refs = load_delivered_refs_file(cycle_id, project_root)
    assert refs["entries"]["decision"]["path"].endswith("decision-doc.md")


def test_v_dc_skip_rr(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-loop-b-002"
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
    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="assumption",
        payload={"text": "Low-risk assumption"},
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
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "R",
        {
            "exit": "loop_b",
            "assumptions": [
                {"id": "A1", "risk": "L", "consequence": "Minor UX gap"},
            ],
        },
    )

    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "V",
            {
                "exit": "dc",
                "batch_confirmed": True,
                "assumptions": [
                    {"id": "A1", "risk": "L", "verification": "Accepted"},
                ],
            },
        )
        == 0
    )

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "DC"
    assert "RR" in gate_state["skipped_gates"]


def test_rr_return_r_rerun(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-loop-b-003"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_loop_b(project_root, cycle_id, stage)

    h_verification = (
        "Method: spike / Owner: dev / Timing: sprint 1 / Release condition: POC passes"
    )
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "V",
        {
            "exit": "rr",
            "assumptions": [
                {"id": "A1", "risk": "H", "verification": h_verification},
            ],
        },
    )

    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="assumption",
        payload={"text": "New risk surfaced during verification"},
    )

    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "RR",
            {
                "exit": "return_r",
                "assumptions": [{"id": "A1", "released": True}],
            },
        )
        == 0
    )

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "R"
    assert gate_state["gates"]["D"]["status"] == "closed"
    assert gate_state["skipped_gates"] == []
