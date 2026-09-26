#!/usr/bin/env python3
"""complete/deliver closes the session and does not write cycle delivered-refs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_WORKFLOW_SCRIPTS = _WORKFLOW_ROOT / "scripts"
for _p in (_DIAG_SCRIPTS, _WORKFLOW_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from cycle_delivered_refs import delivered_refs_file_path  # noqa: E402
from dec_gate_control import (  # noqa: E402
    cmd_deliver,
    cmd_gate_close,
    cmd_init_session,
)
from dec_session_state_schema import session_state_file  # noqa: E402
from dec_test_helpers import render_session_doc  # noqa: E402
from dec_workflow_common import session_base_dir  # noqa: E402
from test_dec_gate_loop_a import _close_qe, _full_template  # noqa: E402


@pytest.fixture
def template_config(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / ".cursor" / "lulu-dev-workflow"
    cfg_dir.mkdir(parents=True)
    local_template = tmp_path / "decision-doc.template.md"
    local_template.write_text(_full_template(), encoding="utf-8")
    cfg_path = cfg_dir / "workflow-config.json"
    cfg_path.write_text(
        json.dumps({"decision": {"decision_doc_template_url": local_template.as_uri()}}),
        encoding="utf-8",
    )
    return tmp_path


def _holder_constraints() -> Path:
    return _WORKFLOW_ROOT / "lulu-approach" / "constraints-feature.json"


def _bring_active_to_dc_then_deliver(
    project_root: Path,
    cycle_id: str,
    stage: str,
) -> None:
    _close_qe(project_root, cycle_id, stage)
    assert (
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
        == 0
    )
    assert (
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


def _assert_complete_without_cycle_refs(
    project_root: Path,
    cycle_id: str,
    stage: str,
    session_dir: Path,
) -> None:
    ss = session_state_file(session_dir).read_text(encoding="utf-8")
    assert "current_state: Completed" in ss
    assert (session_dir / "decision-doc.md").is_file()
    assert not delivered_refs_file_path(cycle_id, project_root).exists()


def test_complete_does_not_write_cycle_refs_on_approach_root(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-approach-complete-001"
    stage = "lulu-approach"
    monkeypatch.chdir(project_root)
    constraints = _holder_constraints()
    session_dir = project_root / session_base_dir(
        cycle_id, stage, project_root=project_root, constraints_path=constraints
    )
    assert (
        cmd_init_session(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints,
            session_dir=session_dir,
        )
        == 0
    )
    _bring_active_to_dc_then_deliver(project_root, cycle_id, stage)
    _assert_complete_without_cycle_refs(project_root, cycle_id, stage, session_dir)


def test_complete_does_not_write_cycle_refs_on_decision_stage(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-decision-complete-001"
    stage = "decision"
    monkeypatch.chdir(project_root)
    assert cmd_init_session(project_root, cycle_id, stage) == 0
    _bring_active_to_dc_then_deliver(project_root, cycle_id, stage)
    session_dir = project_root / session_base_dir(cycle_id, stage, project_root=project_root)
    _assert_complete_without_cycle_refs(project_root, cycle_id, stage, session_dir)
