#!/usr/bin/env python3
"""Tests for global C# / RK# writes, Q fold, and open-risk gate."""

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
)
from dec_register_control import (  # noqa: E402
    cmd_register_append,
    cmd_register_batch_apply,
    cmd_register_commit,
)
from dec_test_helpers import load_gate_payload_file, risk_for_source  # noqa: E402
from dec_workflow_common import registers_path  # noqa: E402
from test_dec_gate_loop_a import _close_o, _full_template  # noqa: E402

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


def _registers(project_root: Path, cycle_id: str, stage: str) -> dict:
    return json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )


def test_constraint_append_revise_remove(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-risk-c1"
    stage = "decision"
    monkeypatch.chdir(project_root)
    cmd_init_session(project_root, cycle_id, stage)
    assert (
        cmd_register_commit(
            project_root,
            cycle_id,
            stage,
            operations=[
                {
                    "action": "append",
                    "kind": "constraint",
                    "payload": {"text": "Must keep SSO"},
                }
            ],
        )
        == 0
    )
    registers = _registers(project_root, cycle_id, stage)
    assert registers["constraints"][0]["id"] == "C1"
    assert registers["constraints"][0]["revision"] == 1
    assert (
        cmd_register_commit(
            project_root,
            cycle_id,
            stage,
            operations=[
                {"action": "revise", "id": "C1", "payload": {"text": "SSO + audit"}}
            ],
        )
        == 0
    )
    registers = _registers(project_root, cycle_id, stage)
    assert registers["constraints"][0]["text"] == "SSO + audit"
    assert registers["constraints"][0]["revision"] == 2
    assert (
        cmd_register_commit(
            project_root,
            cycle_id,
            stage,
            operations=[{"action": "remove", "id": "C1"}],
        )
        == 0
    )
    assert _registers(project_root, cycle_id, stage)["constraints"] == []


def test_register_commit_rejects_risk_write(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-risk-c2"
    stage = "decision"
    monkeypatch.chdir(project_root)
    cmd_init_session(project_root, cycle_id, stage)
    assert (
        cmd_register_commit(
            project_root,
            cycle_id,
            stage,
            operations=[{"action": "append", "kind": "risk", "payload": {"text": "x"}}],
        )
        != 0
    )


def test_apply_r_before_r_writes_rk(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-risk-c3"
    stage = "decision"
    monkeypatch.chdir(project_root)
    cmd_init_session(project_root, cycle_id, stage)
    _close_o(project_root, cycle_id, stage)
    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="assumption",
        payload={"text": "Client accepts the payload"},
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
                        "risk_consequence": "Connect fails",
                    }
                ]
            },
        )
        == 0
    )
    registers = _registers(project_root, cycle_id, stage)
    assert "risk_state" not in registers["assumptions"][0]
    entry = risk_for_source(registers, "A1")
    assert entry["id"] == "RK1"
    assert entry["risk_state"] == "open"
    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "Q",
            {"problem_statement": "problem"},
        )
        != 0
    )
    assert cmd_complete_assumption(
        project_root, cycle_id, stage, entry_id="RK1", release_terms=_H_TERMS
    ) == 0
    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "Q",
            {"problem_statement": "problem"},
        )
        == 0
    )
    assert "constraints" not in load_gate_payload_file(project_root, cycle_id, "Q")


def test_q_fold_legacy_constraints_string(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-risk-c4"
    stage = "decision"
    monkeypatch.chdir(project_root)
    cmd_init_session(project_root, cycle_id, stage)
    _close_o(project_root, cycle_id, stage)
    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "Q",
            {
                "problem_statement": "Export is blocked",
                "constraints": "Must keep SSO\nAnd two tenants",
            },
        )
        == 0
    )
    payload = load_gate_payload_file(project_root, cycle_id, "Q")
    assert payload == {"problem_statement": "Export is blocked"}
    registers = _registers(project_root, cycle_id, stage)
    assert len(registers["constraints"]) == 1
    assert registers["constraints"][0]["text"] == "Must keep SSO\nAnd two tenants"


def test_q_none_does_not_create_constraint(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-risk-c5"
    stage = "decision"
    monkeypatch.chdir(project_root)
    cmd_init_session(project_root, cycle_id, stage)
    _close_o(project_root, cycle_id, stage)
    assert (
        cmd_gate_close(
            project_root,
            cycle_id,
            stage,
            "Q",
            {"problem_statement": "problem", "constraints": "none"},
        )
        == 0
    )
    assert _registers(project_root, cycle_id, stage)["constraints"] == []


def test_rs_batch_rejects_constraint(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-risk-c6"
    stage = "decision"
    monkeypatch.chdir(project_root)
    cmd_init_session(project_root, cycle_id, stage)
    cmd_register_append(
        project_root,
        cycle_id,
        stage,
        register_kind="constraint",
        payload={"text": "Keep SSO"},
    )
    assert (
        cmd_register_batch_apply(
            project_root,
            cycle_id,
            stage,
            operations=[{"id": "C1", "action": "delete"}],
        )
        != 0
    )
    assert _registers(project_root, cycle_id, stage)["constraints"][0]["id"] == "C1"
