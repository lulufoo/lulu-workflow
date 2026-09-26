#!/usr/bin/env python3
"""Tests for get-payload and batch-reclose (RS light-patch batch confirm)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_gate_control import (  # noqa: E402
    cmd_batch_reclose,
    cmd_gate_close,
    cmd_get_payload,
    cmd_init_session,
    cmd_rs_commit,
)
from dec_workflow_common import gate_state_path, registers_path  # noqa: E402
from dec_test_helpers import load_gate_payload_file  # noqa: E402
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


def _close_through_x(project_root: Path, cycle_id: str, stage: str) -> None:
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


def _d_payload(*, rationale: str = "Chose A") -> dict:
    return {
        "decision_rationale": rationale,
        "applies_to": "export",
        "excludes": "mobile",
        "execution_approach": "backend first",
    }


def _x_payload(*, criteria: str = "Users export CSV") -> dict:
    return {
        "acceptance_criteria": criteria,
        "gap": "None",
        "impact_surface": [],
        "external_dependencies": [],
        "key_changes": "Add endpoint",
        "critical_constraints": "none",
        "reversibility": "easy",
    }


def test_get_payload_by_gate(
    template_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = template_config
    cycle_id = "feature-batch-001"
    stage = "decision"
    monkeypatch.chdir(project_root)
    _close_through_x(project_root, cycle_id, stage)

    capsys.readouterr()
    assert cmd_get_payload(project_root, cycle_id, stage, gates=["D"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["payloads"]["D"]["decision_rationale"] == "Chose A"
    assert out["missing"] == []


def test_get_payload_preceding_of(
    template_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = template_config
    cycle_id = "feature-batch-001b"
    stage = "decision"
    monkeypatch.chdir(project_root)
    _close_through_x(project_root, cycle_id, stage)

    capsys.readouterr()
    assert cmd_get_payload(project_root, cycle_id, stage, preceding_of="X") == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert "X" not in out["payloads"]
    assert "X" not in out["requested"]
    assert set(out["requested"]) == {"O", "Q", "GL", "E", "D"}
    assert set(out["payloads"]) == {"O", "Q", "GL", "E", "D"}
    assert out["missing"] == []


def test_get_payload_stale_only(
    template_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = template_config
    cycle_id = "feature-batch-002"
    stage = "decision"
    monkeypatch.chdir(project_root)
    _close_through_x(project_root, cycle_id, stage)
    assert cmd_rs_commit(project_root, cycle_id, stage, "D", operations=[]) == 0

    capsys.readouterr()
    assert cmd_get_payload(project_root, cycle_id, stage, stale_only=True) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert set(out["payloads"]) >= {"D", "X"}
    assert "R" not in out["payloads"]  # R stale but no payload file yet
    assert "R" in out["missing"]


def test_batch_reclose_success(
    template_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project_root = template_config
    cycle_id = "feature-batch-003"
    stage = "decision"
    monkeypatch.chdir(project_root)
    _close_through_x(project_root, cycle_id, stage)
    assert cmd_rs_commit(project_root, cycle_id, stage, "D", operations=[]) == 0

    capsys.readouterr()
    assert (
        cmd_batch_reclose(
            project_root,
            cycle_id,
            stage,
            payloads={
                "D": _d_payload(rationale="Chose A + isolation"),
                "X": _x_payload(criteria="Users export CSV; tenant-isolated"),
            },
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["closed"] == ["D", "X"]
    assert out["active_gate"] == "R"

    state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert state["gates"]["D"]["status"] == "closed"
    assert state["gates"]["X"]["status"] == "closed"
    assert state["gates"]["R"]["status"] == "stale"
    assert state["active_gate"] == "R"

    assert (
        load_gate_payload_file(project_root, cycle_id, "D")["decision_rationale"]
        == "Chose A + isolation"
    )
    assert "tenant-isolated" in load_gate_payload_file(project_root, cycle_id, "X")[
        "acceptance_criteria"
    ]


def test_batch_reclose_invalid_payload_is_atomic(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-batch-004"
    stage = "decision"
    monkeypatch.chdir(project_root)
    _close_through_x(project_root, cycle_id, stage)
    assert cmd_rs_commit(project_root, cycle_id, stage, "D", operations=[]) == 0

    before_d = load_gate_payload_file(project_root, cycle_id, "D")
    before_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )

    assert (
        cmd_batch_reclose(
            project_root,
            cycle_id,
            stage,
            payloads={
                "D": _d_payload(rationale="patched"),
                "X": {"acceptance_criteria": ""},  # invalid
            },
        )
        == 1
    )

    after_d = load_gate_payload_file(project_root, cycle_id, "D")
    after_state = json.loads(
        (project_root / gate_state_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert after_d == before_d
    assert after_state == before_state


def test_batch_reclose_rejects_skip_and_non_align_gates(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-batch-005"
    stage = "decision"
    monkeypatch.chdir(project_root)
    _close_through_x(project_root, cycle_id, stage)
    assert cmd_rs_commit(project_root, cycle_id, stage, "D", operations=[]) == 0

    # Skip D, only X
    assert (
        cmd_batch_reclose(
            project_root,
            cycle_id,
            stage,
            payloads={"X": _x_payload()},
        )
        == 1
    )
    # R not in v1 batch set
    assert (
        cmd_batch_reclose(
            project_root,
            cycle_id,
            stage,
            payloads={
                "D": _d_payload(),
                "X": _x_payload(),
                "R": {"exit": "human_decision", "assumptions": []},
            },
        )
        == 1
    )


def test_rs_to_batch_reclose_integration(
    template_config: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """RS → get-payload (stale) → batch-reclose end-to-end."""
    project_root = template_config
    cycle_id = "feature-batch-006"
    stage = "decision"
    monkeypatch.chdir(project_root)
    _close_through_x(project_root, cycle_id, stage)

    assert cmd_rs_commit(project_root, cycle_id, stage, "Q", operations=[]) == 0
    capsys.readouterr()
    assert cmd_get_payload(project_root, cycle_id, stage, stale_only=True) == 0
    stale = json.loads(capsys.readouterr().out)
    assert "Q" in stale["payloads"]
    assert "E" in stale["payloads"]

    q_payload = dict(stale["payloads"]["Q"])
    q_payload["constraints"] = "tenant isolation"
    gl_payload = dict(stale["payloads"]["GL"])
    e_payload = dict(stale["payloads"]["E"])
    d_payload = dict(stale["payloads"]["D"])
    d_payload["decision_rationale"] = "Chose A under isolation"
    x_payload = dict(stale["payloads"]["X"])

    assert (
        cmd_batch_reclose(
            project_root,
            cycle_id,
            stage,
            payloads={
                "Q": q_payload,
                "GL": gl_payload,
                "E": e_payload,
                "D": d_payload,
                "X": x_payload,
            },
        )
        == 0
    )
    out = json.loads(capsys.readouterr().out)
    assert out["closed"] == ["Q", "GL", "E", "D", "X"]
    assert out["active_gate"] == "R"
    q_closed = load_gate_payload_file(project_root, cycle_id, "Q")
    assert "constraints" not in q_closed
    registers = json.loads(
        (project_root / registers_path(cycle_id, stage)).read_text(encoding="utf-8")
    )
    assert registers["constraints"][0]["text"] == "tenant isolation"
