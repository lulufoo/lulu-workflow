#!/usr/bin/env python3
"""Tests for RS realign (stale) flow, R prior sign-off, and R rs exit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_gate_control import (  # noqa: E402
    cmd_complete_assumption,
    cmd_gate_close,
    cmd_invalidate_from,
    cmd_init_session,
    cmd_rs_commit,
    cmd_stale_from,
)
from dec_register_control import (  # noqa: E402
    cmd_register_append,
    cmd_register_batch_apply,
    cmd_register_update,
)
from dec_session_integrity import cmd_render, run_structural_audit  # noqa: E402
from dec_workflow_common import (  # noqa: E402
    decision_doc_path,
    domain_constraints_path,
    gate_state_path,
    registers_path,
    session_state_path,
)
from dec_test_helpers import gate_payload_exists, risk_for_source  # noqa: E402
from test_dec_gate_loop_a import _close_qe, _full_template  # noqa: E402


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
    stage = "decision"
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
                "exit": "dc",
                "assumptions": [
                    {
                        "id": "A1",
                        "risk_level": "L",
                        "risk_class": "decision",
                        "risk_state": "ignore",
                        "risk_consequence": "minor",
                    }
                ],
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
    stage = "decision"
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
            {"exit": "rs", "realign_gate": "D"},
        )
        == 0
    )

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "R"
    assert gate_state["gates"]["R"]["status"] == "active"


def test_r_exit_rs_accepts_legacy_reopen_gate_key(
    template_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = template_config
    cycle_id = "feature-rs-002b"
    stage = "decision"
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

    capsys.readouterr()
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
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["realign_gate"] == "D"


def test_stale_from_keeps_payloads(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-rs-003"
    stage = "decision"
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

    assert cmd_stale_from(project_root, cycle_id, stage, "D") == 0

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["active_gate"] == "D"
    assert gate_state["gates"]["D"]["status"] == "stale"
    assert gate_state["gates"]["X"]["status"] == "stale"
    assert gate_state["gates"]["R"]["status"] == "stale"
    assert gate_state["gates"]["DC"]["status"] == "pending"

    assert gate_payload_exists(project_root, cycle_id, "D")
    assert gate_payload_exists(project_root, cycle_id, "X")
    assert gate_payload_exists(project_root, cycle_id, "E")

    assert (
        cmd_register_batch_apply(
            project_root,
            cycle_id,
            stage,
            operations=[
                {"id": "P1", "action": "set_state", "state": "verified"},
            ],
        )
        == 0
    )

    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert registers["prior"][0]["state"] == "verified"


def test_rs_commit_atomic_stale(
    template_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = template_config
    cycle_id = "feature-rs-004"
    stage = "decision"
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
            operations=[{"id": "P1", "action": "set_state", "state": "verified"}],
        )
        == 0
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert payload["reenter"] == "D"
    assert payload["active_gate"] == "D"
    assert payload["applied"] == 1
    assert payload["registers"]["prior"][0]["state"] == "verified"
    assert payload["gates"]["D"]["status"] == "stale"
    assert payload["gates"]["X"]["status"] == "stale"
    persisted_registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert payload["registers"] == persisted_registers

    assert gate_payload_exists(project_root, cycle_id, "D")
    assert gate_payload_exists(project_root, cycle_id, "X")


def test_stale_from_d_after_r_closed_preserves_completed_risk(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from dec_register_control import cmd_register_commit  # noqa: WPS433

    project_root = template_config
    cycle_id = "feature-rs-005"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_d(project_root, cycle_id, stage)
    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="assumption",
        payload={"text": "High-risk assumption"},
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
                        "risk_consequence": "blocked",
                    }
                ],
            },
        )
        == 0
    )
    release_terms = (
        "Method: integration test / Owner: QA / Timing: pre-release / "
        "Release condition: export succeeds"
    )
    assert (
        cmd_complete_assumption(
            project_root,
            cycle_id,
            stage,
            entry_id="A1",
            release_terms=release_terms,
            check_result="pass",
            check_evidence="integration test run: export succeeded",
        )
        == 0
    )

    assert cmd_stale_from(project_root, cycle_id, stage, "D") == 0

    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assumption = risk_for_source(registers, "A1")
    assert assumption["risk_level"] == "H"
    assert assumption["risk_consequence"] == "blocked"
    assert assumption["risk_class"] == "decision"
    assert assumption["risk_state"] == "completed"
    assert assumption["release_terms"] == release_terms

    assert (
        cmd_register_update(
            project_root,
            cycle_id,
            stage,
            entry_id="A1",
            payload={"risk_consequence": "must not change during D recovery"},
        )
        == 1
    )

    capsys.readouterr()
    assert cmd_register_commit(project_root, cycle_id, stage, operations=[]) == 0
    context = json.loads(capsys.readouterr().out)
    assert risk_for_source(context["registers"], "A1")["risk_state"] == "completed"

    assert cmd_render(project_root, cycle_id, stage) == 0
    decision_doc = (
        project_root / decision_doc_path(cycle_id, stage)
    ).read_text(encoding="utf-8")
    assert release_terms in decision_doc
    audit_errors = run_structural_audit(project_root, cycle_id, stage)
    assert not any("REG_RISK_WHEN_R_OPEN" in error for error in audit_errors)


def test_rs_commit_validation_failure_changes_no_session_artifact(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = template_config
    cycle_id = "feature-rs-005b"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_d(project_root, cycle_id, stage)
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

    artifacts = [
        project_root / gate_state_path(cycle_id, stage),
        project_root / registers_path(cycle_id, stage),
        project_root / session_state_path(cycle_id, stage),
    ]
    before = {
        path: path.read_text(encoding="utf-8") if path.exists() else None
        for path in artifacts
    }

    assert (
        cmd_rs_commit(
            project_root,
            cycle_id,
            stage,
            "D",
            operations=[{"id": "P999", "action": "delete"}],
        )
        == 1
    )
    after = {
        path: path.read_text(encoding="utf-8") if path.exists() else None
        for path in artifacts
    }
    assert after == before

    constraints_file = project_root / domain_constraints_path(cycle_id, stage)
    constraints_file.write_text("{", encoding="utf-8")
    assert cmd_rs_commit(project_root, cycle_id, stage, "D", operations=[]) == 1
    after_context_failure = {
        path: path.read_text(encoding="utf-8") if path.exists() else None
        for path in artifacts
    }
    assert after_context_failure == before


def test_stale_r_dc_requires_confirmed_review_receipt(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = template_config
    cycle_id = "feature-rs-005c"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_d(project_root, cycle_id, stage)
    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="assumption",
        payload={"text": "High-risk assumption"},
    )
    x_payload = {
        "acceptance_criteria": "Users export CSV",
        "gap": "None",
        "impact_surface": [],
        "external_dependencies": [],
        "key_changes": "Add endpoint",
        "critical_constraints": "none",
        "reversibility": "easy",
    }
    cmd_gate_close(project_root, cycle_id, stage, "X", x_payload)
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
                    "risk_consequence": "blocked",
                }
            ],
        },
    )
    cmd_complete_assumption(
        project_root,
        cycle_id,
        stage,
        entry_id="A1",
        release_terms=(
            "Method: integration test / Owner: QA / Timing: pre-release / "
            "Release condition: export succeeds"
        ),
        check_result="pass",
        check_evidence="integration test run: export succeeded",
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

    assert cmd_stale_from(project_root, cycle_id, stage, "D") == 0
    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "D",
            {
                "decision_rationale": "Chose A updated",
                "applies_to": "export",
                "excludes": "mobile",
                "execution_approach": "backend first",
            },
        )
        == 0
    )
    assert cmd_gate_close(project_root, cycle_id, stage, "X", x_payload) == 0

    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "R",
            {"exit": "human_decision", "assumptions": []},
        )
        == 0
    )
    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "R",
            {"exit": "rs", "realign_gate": "D", "assumptions": []},
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
        == 1
    )
    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "R",
            {
                "exit": "dc",
                "assumptions": [],
                "stale_review": {
                    "user_confirmed": False,
                    "affected_ids": ["A1"],
                    "dispositions": {"A1": "keep_completed"},
                },
            },
        )
        == 1
    )
    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "R",
            {
                "exit": "dc",
                "assumptions": [],
                "stale_review": {
                    "user_confirmed": True,
                    "affected_ids": ["A1"],
                    "dispositions": {"A1": "keep_completed"},
                },
            },
        )
        == 0
    )


def test_gate_close_preserves_downstream_stale(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-rs-006"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_d(project_root, cycle_id, stage)
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
    assert cmd_stale_from(project_root, cycle_id, stage, "D") == 0

    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "D",
            {
                "decision_rationale": "Chose A updated",
                "applies_to": "export",
                "excludes": "mobile",
                "execution_approach": "backend first",
            },
        )
        == 0
    )

    gate_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert gate_state["gates"]["D"]["status"] == "closed"
    assert gate_state["active_gate"] == "X"
    assert gate_state["gates"]["X"]["status"] == "stale"


def test_invalidate_from_removed(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-rs-007"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _close_through_d(project_root, cycle_id, stage)
    assert cmd_invalidate_from(project_root, cycle_id, stage, "D") == 1
