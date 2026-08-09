#!/usr/bin/env python3
"""Tests for complete-assumption and set-risk-state CLI subcommands."""

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
    cmd_complete_assumption,
    cmd_gate_close,
    cmd_init_session,
    cmd_set_risk_state,
)
from dec_gate_state_schema import load_gate_state  # noqa: E402
from dec_register_control import cmd_register_append, cmd_register_update  # noqa: E402
from dec_workflow_common import gate_state_path, registers_path  # noqa: E402
from test_dec_gate_loop_a import _close_qe, _full_template  # noqa: E402

_H_TERMS = (
    "Method: integration test / Owner: QA / Timing: pre-release / "
    "Release condition: export succeeds"
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


def _reach_active_r(project_root: Path, cycle_id: str, stage: str) -> None:
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


def _close_through_r_active(project_root: Path, cycle_id: str, stage: str) -> None:
    _reach_active_r(project_root, cycle_id, stage)
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


def test_apply_r_assumptions_without_closing(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-apply-r"
    stage = "decision"
    monkeypatch.chdir(project_root)
    _reach_active_r(project_root, cycle_id, stage)

    assert (
        cmd_apply_r_assumptions(
            project_root,
            cycle_id,
            stage,
            {
                "assumptions": [
                    {
                        "id": "A1",
                        "risk_level": "H",
                        "risk_class": "decision",
                        "risk_state": "open",
                        "risk_consequence": "Export blocked",
                    }
                ]
            },
        )
        == 0
    )
    state = load_gate_state(project_root / gate_state_path(cycle_id, stage))
    assert state["active_gate"] == "R"
    assert state["gates"]["R"]["status"] == "active"
    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert registers["assumptions"][0]["risk_state"] == "open"


def test_complete_assumption_during_active_r(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a1"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)

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

    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    entry = registers["assumptions"][0]
    assert entry["risk_state"] == "completed"
    assert entry["release_terms"] == _H_TERMS


def test_reopening_completed_risk_clears_release_terms(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a1b"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)
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
        cmd_set_risk_state(
            project_root,
            cycle_id,
            stage,
            entry_id="A1",
            risk_state="open",
        )
        == 0
    )

    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    entry = registers["assumptions"][0]
    assert entry["risk_state"] == "open"
    assert "release_terms" not in entry


def test_apply_r_reopening_completed_risk_clears_release_terms(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a1c"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)
    cmd_complete_assumption(
        project_root,
        cycle_id,
        stage,
        entry_id="A1",
        release_terms=_H_TERMS,
    )
    assert (
        cmd_apply_r_assumptions(
            project_root,
            cycle_id,
            stage,
            {
                "assumptions": [
                    {
                        "id": "A1",
                        "risk_level": "H",
                        "risk_class": "decision",
                        "risk_state": "open",
                        "risk_consequence": "Updated evidence invalidates release",
                    }
                ]
            },
        )
        == 0
    )

    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    entry = registers["assumptions"][0]
    assert entry["risk_state"] == "open"
    assert "release_terms" not in entry


def test_register_update_reopening_completed_risk_clears_release_terms(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a1d"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)
    cmd_complete_assumption(
        project_root,
        cycle_id,
        stage,
        entry_id="A1",
        release_terms=_H_TERMS,
    )
    assert (
        cmd_register_update(
            project_root,
            cycle_id,
            stage,
            entry_id="A1",
            payload={"risk_state": "open"},
        )
        == 0
    )

    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    entry = registers["assumptions"][0]
    assert entry["risk_state"] == "open"
    assert "release_terms" not in entry


def test_complete_assumption_accepts_literal(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a2"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)
    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    registers["assumptions"][0]["risk_level"] = "L"
    (project_root / registers_path(cycle_id, stage)).write_text(
        json.dumps(registers, indent=2), encoding="utf-8"
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


def test_complete_assumption_rejects_handoff(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a3"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)
    assert (
        cmd_complete_assumption(
            project_root,
            cycle_id,
            stage,
            entry_id="A1",
            release_terms="Handoff: QA team",
        )
        != 0
    )


def test_complete_assumption_requires_open_state(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a4"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)
    cmd_complete_assumption(
        project_root, cycle_id, stage, entry_id="A1", release_terms="Accepted"
    )
    assert (
        cmd_complete_assumption(
            project_root,
            cycle_id,
            stage,
            entry_id="A1",
            release_terms="Accepted",
        )
        != 0
    )


def test_set_risk_state_ignore_and_open(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a5"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)
    assert (
        cmd_set_risk_state(
            project_root, cycle_id, stage, entry_id="A1", risk_state="ignore"
        )
        == 0
    )
    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert registers["assumptions"][0]["risk_state"] == "ignore"

    assert (
        cmd_set_risk_state(
            project_root, cycle_id, stage, entry_id="A1", risk_state="open"
        )
        == 0
    )


def test_set_risk_state_rejects_none_triad(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a6"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)
    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    registers["assumptions"].append(
        {
            "id": "A2",
            "text": "non risk",
            "source": "R",
            "risk_level": "none",
            "risk_class": "none",
            "risk_state": "none",
        }
    )
    (project_root / registers_path(cycle_id, stage)).write_text(
        json.dumps(registers, indent=2), encoding="utf-8"
    )

    assert (
        cmd_set_risk_state(
            project_root, cycle_id, stage, entry_id="A2", risk_state="ignore"
        )
        != 0
    )


def test_apply_r_defaults_l_to_ignore(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a6d"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _reach_active_r(project_root, cycle_id, stage)
    assert (
        cmd_apply_r_assumptions(
            project_root,
            cycle_id,
            stage,
            payload={
                "assumptions": [
                    {
                        "id": "A1",
                        "risk_level": "L",
                        "risk_class": "decision",
                        "risk_consequence": "Minor",
                    }
                ]
            },
        )
        == 0
    )
    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert registers["assumptions"][0]["risk_state"] == "ignore"


def test_register_update_rejects_completed(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a6c"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)
    assert (
        cmd_apply_r_assumptions(
            project_root,
            cycle_id,
            stage,
            payload={
                "assumptions": [
                    {
                        "id": "A1",
                        "risk_level": "H",
                        "risk_class": "decision",
                        "risk_state": "open",
                        "risk_consequence": "May fail",
                    }
                ]
            },
        )
        == 0
    )
    assert (
        cmd_register_update(
            project_root,
            cycle_id,
            stage,
            entry_id="A1",
            payload={"risk_state": "completed"},
        )
        != 0
    )
    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert registers["assumptions"][0]["risk_state"] == "open"


def test_gate_close_rejects_invented_completed(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a6b"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)
    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "R",
            {
                "exit": "dc",
                "assumptions": [
                    {
                        "id": "A1",
                        "risk_level": "H",
                        "risk_class": "decision",
                        "risk_state": "completed",
                        "risk_consequence": "May fail",
                        "release_terms": "Accepted",
                    }
                ],
            },
        )
        != 0
    )
    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert registers["assumptions"][0].get("risk_state") != "completed"


def test_rr_gate_close_rejected(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a7"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)
    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "RR",
            {"exit": "dc", "assumptions": []},
        )
        != 0
    )


def test_r_dc_forbids_open_risk_state(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a8"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_r_active(project_root, cycle_id, stage)
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

    cmd_complete_assumption(
        project_root, cycle_id, stage, entry_id="A1", release_terms="Accepted"
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


def test_all_ignore_allows_r_to_dc(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a9"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _reach_active_r(project_root, cycle_id, stage)
    assert (
        cmd_apply_r_assumptions(
            project_root,
            cycle_id,
            stage,
            payload={
                "assumptions": [
                    {
                        "id": "A1",
                        "risk_level": "L",
                        "risk_class": "decision",
                        "risk_state": "ignore",
                        "risk_consequence": "Minor",
                    }
                ]
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
            {"exit": "dc", "assumptions": []},
        )
        == 0
    )
    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "DC"


def test_changing_risk_level_keeps_risk_state(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-complete-a10"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _reach_active_r(project_root, cycle_id, stage)
    assert (
        cmd_apply_r_assumptions(
            project_root,
            cycle_id,
            stage,
            payload={
                "assumptions": [
                    {
                        "id": "A1",
                        "risk_level": "H",
                        "risk_class": "decision",
                        "risk_state": "ignore",
                        "risk_consequence": "May fail",
                    }
                ]
            },
        )
        == 0
    )
    assert (
        cmd_register_update(
            project_root,
            cycle_id,
            stage,
            entry_id="A1",
            payload={"risk_level": "M"},
        )
        == 0
    )
    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert registers["assumptions"][0]["risk_level"] == "M"
    assert registers["assumptions"][0]["risk_state"] == "ignore"
