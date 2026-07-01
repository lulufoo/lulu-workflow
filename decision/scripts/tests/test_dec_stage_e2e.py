#!/usr/bin/env python3
"""E2E smoke tests for lulu-bet and lulu-approach stage paths."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_domain_constraints_schema import load_domain_constraints  # noqa: E402
from dec_gate_control import cmd_init_session, cmd_resolve_context  # noqa: E402
from dec_workflow_common import (  # noqa: E402
    domain_constraints_path,
    gate_state_path,
    session_base_dir,
)
from test_dec_gate_loop_a import _full_template  # noqa: E402

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]


def _holder_constraints(stage: str) -> Path:
    return _WORKFLOW_ROOT / stage / "constraints-feature.json"


@pytest.fixture
def template_config(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / "skill-config" / "lulu-dev-workflow"
    cfg_dir.mkdir(parents=True)
    local_template = tmp_path / "decision-doc.template.md"
    local_template.write_text(_full_template(), encoding="utf-8")
    (cfg_dir / "workflow-config.json").write_text(
        json.dumps({"decision": {"decision_doc_template_url": local_template.as_uri()}}),
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize(
    ("stage", "expected_subdir"),
    [
        ("lulu-bet", "lulu-bet"),
        ("lulu-approach", "lulu-approach"),
    ],
)
def test_stage_init_and_constraints(
    template_config: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    expected_subdir: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project_root = template_config
    cycle_id = f"e2e-{stage.replace('-', '_')}"
    constraints_path = _holder_constraints(stage)
    monkeypatch.chdir(project_root)

    assert (
        cmd_init_session(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
        )
        == 0
    )
    capsys.readouterr()
    session_dir = project_root / session_base_dir(
        cycle_id,
        stage,
        project_root=project_root,
        constraints_path=constraints_path,
    )
    assert expected_subdir in session_dir.as_posix()
    assert (session_dir / "gate-state.json").exists()

    assert (
        cmd_resolve_context(
            project_root,
            cycle_id,
            stage,
            constraints_path=constraints_path,
        )
        == 0
    )
    ctx = json.loads(capsys.readouterr().out)
    assert ctx["stage"] == stage
    assert ctx["domain_constraints"]["stage"] == stage
    assert ctx["domain_constraints"]["cache_subdir"] == expected_subdir
    assert "after_dc" in ctx

    if stage == "lulu-approach":
        constraints = load_domain_constraints(
            project_root / domain_constraints_path(
                cycle_id,
                stage,
                project_root=project_root,
                constraints_path=constraints_path,
            )
        )
        assert "impact_surface" in constraints["x_dimensions"]
        assert constraints.get("context_loading")

    gate_state = json.loads(
        (project_root / gate_state_path(
            cycle_id,
            stage,
            project_root=project_root,
            constraints_path=constraints_path,
        )).read_text(encoding="utf-8")
    )
    assert gate_state["stage"] == stage
