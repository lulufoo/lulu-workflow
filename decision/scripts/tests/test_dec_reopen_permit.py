#!/usr/bin/env python3
"""Tests for $DEC_REOPEN --permit under holder_required authorization."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

_DIAG = Path(__file__).resolve().parents[1]
_APPROACH_SCRIPTS = Path(__file__).resolve().parents[3] / "lulu-approach" / "scripts"
_APPROACH_SCHEMA = _APPROACH_SCRIPTS / "schema"
_WORKFLOW_SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"
_CONSTRAINTS = Path(__file__).resolve().parents[3] / "lulu-approach" / "constraints-feature.json"

for _p in (_DIAG, _APPROACH_SCRIPTS, _APPROACH_SCHEMA, _WORKFLOW_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from dec_gate_control import cmd_reopen  # noqa: E402
from dec_session_state_schema import read_current_state, write_session_state  # noqa: E402
from platform_schema import detect_platform  # noqa: E402
from platforms.paths import cache_dir as platform_cache_dir  # noqa: E402
from test_dec_gate_loop_a import _full_template  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_tree = _load(
    "approach_dependency_tree_schema",
    _APPROACH_SCHEMA / "approach_dependency_tree_schema.py",
)
_ctrl = _load("approach_shell_control", _APPROACH_SCRIPTS / "approach_shell_control.py")


def _write_template_config(project_root: Path) -> None:
    config_dir = project_root / "skill-config" / "lulu-dev-workflow"
    config_dir.mkdir(parents=True)
    template = project_root / "decision-doc.template.md"
    template.write_text(_full_template(), encoding="utf-8")
    (config_dir / "workflow-config.json").write_text(
        json.dumps({"decision": {"decision_doc_template_url": template.as_uri()}}),
        encoding="utf-8",
    )


def _prepared(project_root: Path, cycle_id: str) -> Path:
    root = project_root / platform_cache_dir(detect_platform()) / cycle_id / "lulu-approach"
    _ctrl.init_shell(root)
    (root / "main" / "decision-doc.md").write_text("# Main\n", encoding="utf-8")
    write_session_state(root / "main" / "session-state.md", "Delivered")
    _ctrl.enter_split(root)
    _ctrl.mark_split_delivered(root)
    _ctrl.enter_working(root, ["D1", "D2"], focus="D1")
    _tree.save_dependency_tree(
        root,
        _tree.build_tree(
            nodes=[
                {"id": "D1", "title": "one", "summary": "s1"},
                {"id": "D2", "title": "two", "summary": "s2"},
            ],
            edges=[{"from": "D2", "to": "D1"}],
            order=["D1", "D2"],
            status="locked",
        ),
    )
    return root


def test_holder_required_rejects_without_permit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-reopen-permit-001"
    root = _prepared(project_root, cycle_id)
    _ctrl.enter_node(
        root,
        "D1",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )
    write_session_state(root / "D1" / "session-state.md", "Delivered")
    err = io.StringIO()
    with redirect_stderr(err), redirect_stdout(io.StringIO()):
        rc = cmd_reopen(
            project_root,
            cycle_id,
            "lulu-approach",
            constraints_path=_CONSTRAINTS,
        )
    assert rc == 1
    assert "holder_required" in err.getvalue()


def test_holder_required_consumes_permit_and_freezes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-reopen-permit-002"
    root = _prepared(project_root, cycle_id)
    _ctrl.enter_node(
        root,
        "D1",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )
    _ctrl.mark_node_delivered(root, "D1")
    write_session_state(root / "D1" / "session-state.md", "Delivered")
    _ctrl.enter_node(
        root,
        "D2",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )
    result = _ctrl.reopen_node(
        root,
        "D1",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )
    permit = Path(result["permit_path"])
    assert json.loads(permit.read_text(encoding="utf-8"))["state"] == "issued"
    assert read_current_state(root / "D1" / "session-state.md") == "Completed"

    out = io.StringIO()
    with redirect_stdout(out):
        rc = cmd_reopen(
            project_root,
            cycle_id,
            "lulu-approach",
            constraints_path=_CONSTRAINTS,
            permit_path=permit,
        )
    assert rc == 0
    payload = json.loads(out.getvalue())
    assert payload["session_state"] == "Frozen"
    assert payload["permit_state"] == "consumed"
    assert read_current_state(root / "D1" / "session-state.md") == "Frozen"
    assert json.loads(permit.read_text(encoding="utf-8"))["state"] == "consumed"

    err = io.StringIO()
    with redirect_stderr(err), redirect_stdout(io.StringIO()):
        rc2 = cmd_reopen(
            project_root,
            cycle_id,
            "lulu-approach",
            constraints_path=_CONSTRAINTS,
            permit_path=permit,
        )
    assert rc2 == 1
    assert "issued" in err.getvalue()
