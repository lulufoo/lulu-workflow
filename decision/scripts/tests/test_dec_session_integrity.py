#!/usr/bin/env python3
"""Tests for dec_session_integrity audit and render."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_gate_control import cmd_check_delivery_ready, cmd_gate_close, cmd_init_session  # noqa: E402
from dec_register_schema import strip_assumption_risk_fields  # noqa: E402
from dec_session_integrity import cmd_audit, cmd_render, run_structural_audit  # noqa: E402
from dec_workflow_common import decision_doc_path  # noqa: E402
from dec_test_helpers import gate_payload_exists, load_rendered_doc  # noqa: E402
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


def test_strip_assumption_risk_fields() -> None:
    data = {
        "version": "1",
        "cycle_id": "c",
        "stage": "decision",
        "prior": [],
        "assumptions": [{"id": "A1", "text": "t", "state": "pending", "source": "R", "risk": "H", "consequence": "x"}],
        "next_prior_seq": 1,
        "next_assumption_seq": 2,
    }
    stripped = strip_assumption_risk_fields(data)
    assert "risk" not in stripped["assumptions"][0]
    assert "consequence" not in stripped["assumptions"][0]


def test_structural_audit_passes_with_payloads(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-integrity-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    cmd_init_session(project_root, cycle_id, stage)
    _close_qe(project_root, cycle_id, stage)

    errors = run_structural_audit(project_root, cycle_id, stage)
    assert errors == []


def test_render_creates_decision_doc(template_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = template_config
    cycle_id = "feature-integrity-002"
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
            "decision_rationale": "Chose A",
            "applies_to": "export",
            "excludes": "mobile",
            "execution_approach": "backend first",
        },
    )

    doc_path = project_root / decision_doc_path(cycle_id, stage)
    assert not doc_path.exists()
    assert gate_payload_exists(project_root, cycle_id, "D")

    assert cmd_render(project_root, cycle_id, stage) == 0
    doc = load_rendered_doc(project_root, cycle_id, stage)
    assert "Chose A" in doc
    assert "backend first" in doc


def test_audit_cli_output(template_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    project_root = template_config
    cycle_id = "feature-integrity-003"
    stage = "decision"
    monkeypatch.chdir(project_root)

    cmd_init_session(project_root, cycle_id, stage)
    _close_qe(project_root, cycle_id, stage)
    capsys.readouterr()

    assert cmd_audit(project_root, cycle_id, stage, mode="structural") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["passed"] is True
    assert payload["errors"] == []
