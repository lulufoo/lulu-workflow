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


def test_decision_fact_audit_before_deliver_reports_missing(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = template_config
    cycle_id = "feature-integrity-004"
    stage = "decision"
    monkeypatch.chdir(project_root)

    cmd_init_session(project_root, cycle_id, stage)
    _close_qe(project_root, cycle_id, stage)
    capsys.readouterr()

    assert cmd_audit(project_root, cycle_id, stage, mode="decision-fact") == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["passed"] is False
    assert any("not found" in e for e in payload["errors"])


def _init_nested_d1_active(
    project_root: Path, cycle_id: str, stage: str = "decision"
) -> Path:
    """Bootstrap nested D1 as Active; outer must not hold gate-state."""
    from dec_active_control import _commit_active
    from dec_session_state_schema import session_state_file, write_session_state
    from dec_workflow_common import session_base_dir

    outer = project_root / session_base_dir(cycle_id, stage, project_root=project_root)
    nested = outer / "D1"
    assert (
        cmd_init_session(
            project_root,
            cycle_id,
            stage,
            session_dir=nested,
            domain_override={"node_id": "D1", "session_role": "sub"},
            commit_active=False,
        )
        == 0
    )
    write_session_state(session_state_file(nested), "InProgress")
    _commit_active(project_root, cycle_id, stage, session_dir=nested)
    assert not (outer / "gate-state.json").exists()
    assert (nested / "gate-state.json").is_file()
    return nested


def test_structural_audit_follows_active_nested_d1(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Integrity must read Active D1, not stage outer (archive-1.1 A3)."""
    project_root = template_config
    cycle_id = "feature-integrity-active-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    nested = _init_nested_d1_active(project_root, cycle_id, stage)
    errors = run_structural_audit(project_root, cycle_id, stage)
    assert errors == []
    outer = nested.parent
    assert not (outer / "gate-state.json").exists()


def test_check_delivery_ready_follows_active_nested_d1(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """check-delivery-ready must not FileNotFound on outer when Active is D1."""
    project_root = template_config
    cycle_id = "feature-integrity-active-002"
    stage = "decision"
    monkeypatch.chdir(project_root)

    _init_nested_d1_active(project_root, cycle_id, stage)
    capsys.readouterr()
    assert cmd_check_delivery_ready(project_root, cycle_id, stage) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["ready"] is False
    assert all("gate-state not found" not in e for e in payload["errors"])


def test_render_writes_decision_doc_under_active_nested_d1(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-integrity-active-003"
    stage = "decision"
    monkeypatch.chdir(project_root)

    nested = _init_nested_d1_active(project_root, cycle_id, stage)
    _close_qe(project_root, cycle_id, stage)
    cmd_gate_close(
        project_root,
        cycle_id,
        stage,
        "D",
        {
            "decision_rationale": "Nested choose A",
            "applies_to": "export",
            "excludes": "mobile",
            "execution_approach": "backend first",
        },
    )

    assert cmd_render(project_root, cycle_id, stage) == 0
    doc_path = nested / "decision-doc.md"
    assert doc_path.is_file()
    assert "Nested choose A" in doc_path.read_text(encoding="utf-8")
    assert not (nested.parent / "decision-doc.md").exists()
