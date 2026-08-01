#!/usr/bin/env python3
"""Nested approach deliver must not steal cycle delivered-refs (archive-1.1)."""

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

from cycle_delivered_refs import (  # noqa: E402
    delivered_refs_file_path,
    load_delivered_refs_file,
)
from dec_active_control import _commit_active  # noqa: E402
from dec_gate_control import (  # noqa: E402
    cmd_deliver,
    cmd_gate_close,
    cmd_init_session,
)
from dec_session_paths import skips_cycle_delivered_ref_on_deliver  # noqa: E402
from dec_session_state_schema import session_state_file, write_session_state  # noqa: E402
from dec_test_helpers import render_session_doc  # noqa: E402
from dec_workflow_common import session_base_dir  # noqa: E402
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


def _holder_constraints() -> Path:
    return _WORKFLOW_ROOT / "lulu-approach" / "constraints-feature.json"


def test_skips_cycle_ref_helper_nested_approach_only(tmp_path: Path) -> None:
    approach = tmp_path / "lulu-approach"
    (approach / "D1").mkdir(parents=True)
    (approach / "main").mkdir(parents=True)
    flat = tmp_path / "decision"
    flat.mkdir()
    other_nested = tmp_path / "decision" / "D1"
    other_nested.mkdir(parents=True)

    assert skips_cycle_delivered_ref_on_deliver(approach / "D1") is True
    assert skips_cycle_delivered_ref_on_deliver(approach / "main") is True
    assert skips_cycle_delivered_ref_on_deliver(flat) is False
    assert skips_cycle_delivered_ref_on_deliver(other_nested) is False


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


def test_nested_approach_deliver_skips_cycle_delivered_refs(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-nested-deliver-001"
    stage = "lulu-approach"
    monkeypatch.chdir(project_root)
    constraints = _holder_constraints()

    outer = project_root / session_base_dir(
        cycle_id, stage, project_root=project_root, constraints_path=constraints
    )
    nested = outer / "D1"
    assert (
        cmd_init_session(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints,
            session_dir=nested,
            domain_override={"node_id": "D1", "session_role": "sub"},
            commit_active=False,
        )
        == 0
    )
    write_session_state(session_state_file(nested), "InProgress")
    _commit_active(project_root, cycle_id, stage, session_dir=nested, constraints_path=constraints)

    _bring_active_to_dc_then_deliver(project_root, cycle_id, stage)

    ss = session_state_file(nested).read_text(encoding="utf-8")
    assert "current_state: Completed" in ss
    assert (nested / "decision-doc.md").is_file()
    assert (nested / "decision-fact.json").is_file()

    refs_path = delivered_refs_file_path(cycle_id, project_root)
    assert not refs_path.exists()


def test_flat_decision_deliver_still_writes_cycle_refs(
    template_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = template_config
    cycle_id = "feature-flat-deliver-001"
    stage = "decision"
    monkeypatch.chdir(project_root)

    assert cmd_init_session(project_root, cycle_id, stage) == 0
    _bring_active_to_dc_then_deliver(project_root, cycle_id, stage)

    refs = load_delivered_refs_file(cycle_id, project_root)
    entry = refs["entries"]["decision"]
    assert entry["path"].endswith("decision-doc.md")
    assert "D1/" not in entry["path"]
