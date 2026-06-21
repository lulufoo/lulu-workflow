#!/usr/bin/env python3
"""Tests for RS reopen flow, R prior sign-off, and R rs exit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dx_decision_doc_schema import load_decision_doc  # noqa: E402
from dx_gate_control import (  # noqa: E402
    cmd_gate_close,
    cmd_invalidate_from,
    cmd_init_session,
    cmd_rs_commit,
)
from dx_register_control import cmd_register_append, cmd_register_batch_apply  # noqa: E402
from dx_workflow_common import decision_doc_path, gate_state_path, registers_path  # noqa: E402
from test_dx_gate_loop_a import _close_qe, _full_template  # noqa: E402


@pytest.fixture
def template_config(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / "skill-config" / "lulu-dev-workflow"
    cfg_dir.mkdir(parents=True)
    local_template = tmp_path / "decision-doc.template.md"
    local_template.write_text(_full_template(), encoding="utf-8")
    cfg_path = cfg_dir / "workflow-config.json"
    cfg_path.write_text(
        json.dumps({"diagnostic": {"decision_doc_template_url": local_template.as_uri()}}),
        encoding="utf-8",
    )
    return tmp_path


def _close_through_d(project_root: Path, cycle_id: str, stage: str) -> None:
    cmd_init_session(project_root, cycle_id, stage)
    _close_qe(project_root, cycle_id, stage)
    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="prior",
        payload={"kind": "preference", "text": "Prefer incremental rollout"},
    )
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "D",
        {
            "decision_rationale": "Chose A",
            "applies_to": "export",
            "excludes": "mobile",
            "execution_approach": "backend first",
        },
    )


def test_r_prior_signoff_on_close(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-rs-001"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)

    _close_through_d(project_root, cycle_id, stage)
    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="assumption",
        payload={"text": "API ready"},
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
            {
                "exit": "loop_b",
                "assumptions": [{"id": "A1", "risk": "L", "consequence": "minor"}],
            },
        )
        == 0
    )

    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    prior_states = [e["state"] for e in registers["prior"]]
    assert all(state == "verified" for state in prior_states)


def test_r_exit_rs_does_not_close_gate(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-rs-002"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)

    _close_through_d(project_root, cycle_id, stage)
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
            {"exit": "rs", "reopen_gate": "D"},
        )
        == 0
    )

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "R"
    assert gate_state["gates"]["R"]["status"] == "active"


def test_rs_invalidate_and_register_batch(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-rs-003"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)

    _close_through_d(project_root, cycle_id, stage)
    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="assumption",
        payload={"text": "Stale assumption from X"},
    )
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "X",
        {
            "acceptance_criteria": "Users export CSV",
            "gap": "None",
            "impact_surface": [],
            "external_dependencies": [],
            "key_changes": "Add endpoint",
            "critical_constraints": "none",
            "reversibility": "easy",
        },
    )

    assert cmd_invalidate_from(project_root, cycle_id, stage, "D") == 0

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "D"
    assert gate_state["gates"]["D"]["status"] == "active"
    assert gate_state["gates"]["X"]["status"] == "invalidated"

    doc = load_decision_doc(project_root / decision_doc_path(cycle_id, stage))
    assert "Add endpoint" not in doc
    assert "Chose A" not in doc

    assert (
        cmd_register_batch_apply(
            project_root,
            cycle_id,
            stage,
            operations=[
                {"id": "A1", "action": "set_state", "state": "pending"},
            ],
        )
        == 0
    )

    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert registers["assumptions"][0]["state"] == "pending"


def test_rs_commit_atomic(template_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    project_root = template_config
    cycle_id = "feature-rs-004"
    stage = "diagnostic"
    monkeypatch.chdir(project_root)

    _close_through_d(project_root, cycle_id, stage)
    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="assumption",
        payload={"text": "Stale assumption from X"},
    )
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "X",
        {
            "acceptance_criteria": "Users export CSV",
            "gap": "None",
            "impact_surface": [],
            "external_dependencies": [],
            "key_changes": "Add endpoint",
            "critical_constraints": "none",
            "reversibility": "easy",
        },
    )

    capsys.readouterr()
    assert (
        cmd_rs_commit(
            project_root,
            cycle_id,
            stage,
            "D",
            operations=[{"id": "A1", "action": "set_state", "state": "pending"}],
        )
        == 0
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["reenter"] == "D"
    assert payload["active_gate"] == "D"
    assert payload["applied"] == 1
    assert payload["registers"]["assumptions"][0]["state"] == "pending"
    assert payload["gates"]["D"]["status"] == "active"
    assert payload["gates"]["X"]["status"] == "invalidated"

    doc = load_decision_doc(project_root / decision_doc_path(cycle_id, stage))
    assert "Add endpoint" not in doc
    assert "Chose A" not in doc
