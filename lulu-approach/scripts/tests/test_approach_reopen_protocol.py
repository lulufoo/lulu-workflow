#!/usr/bin/env python3
"""Tests for approach's permit-backed reopen preparation protocol."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_SCHEMA = _SCRIPTS / "schema"
_WORKFLOW_SCRIPTS = _SCRIPTS.parents[1] / "scripts"
_DECISION_SCRIPTS = _SCRIPTS.parents[1] / "decision" / "scripts"
_CONSTRAINTS = _SCRIPTS.parent / "constraints-feature.json"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_schema = _load("approach_shell_schema", _SCHEMA / "approach_shell_schema.py")
_tree = _load(
    "approach_dependency_tree_schema", _SCHEMA / "approach_dependency_tree_schema.py"
)
_binding = _load(
    "approach_node_binding_schema", _SCHEMA / "approach_node_binding_schema.py"
)

for _path in (_SCRIPTS, _SCHEMA, _WORKFLOW_SCRIPTS, _DECISION_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
_ctrl = _load("approach_shell_control", _SCRIPTS / "approach_shell_control.py")

from dec_active_session_schema import load_active_session  # noqa: E402
from dec_session_state_schema import read_current_state, write_session_state  # noqa: E402
from platforms.paths import cache_dir as platform_cache_dir  # noqa: E402
from platform_schema import detect_platform  # noqa: E402


def _full_template() -> str:
    return (
        "# Decision: {title}\n\n"
        "## 1. User Prior\n\n- placeholder\n\n"
        "## 2. Problem Definition\n\nTBD\n\n"
        "## 3. Direction Comparison\n\nTBD\n\n"
        "## 4. Decision Rationale\n\nTBD\n\n"
        "## 5. Scope\n\nTBD\n\n"
        "## 6. Assumptions & Risks\n\nTBD\n\n"
        "## 7. Execution Analysis\n\n### 7.1 Acceptance Criteria\n\nTBD\n"
    )


def _write_template_config(project_root: Path) -> None:
    config_dir = project_root / "skill-config" / "lulu-dev-workflow"
    config_dir.mkdir(parents=True)
    template = project_root / "decision-doc.template.md"
    template.write_text(_full_template(), encoding="utf-8")
    (config_dir / "workflow-config.json").write_text(
        json.dumps({"decision": {"decision_doc_template_url": template.as_uri()}}),
        encoding="utf-8",
    )


def _prepared_chain(project_root: Path, cycle_id: str) -> Path:
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


def test_reopen_freezes_successor_session_issues_permit_and_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-reopen-protocol-001"
    root = _prepared_chain(project_root, cycle_id)

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

    permit_path = Path(result["permit_path"])
    assert permit_path.is_file()
    permit = json.loads(permit_path.read_text(encoding="utf-8"))
    assert permit["state"] == "issued"
    assert permit["node_id"] == "D1"
    assert result["shell"]["focus"] == "D1"
    assert load_active_session(root)["session_dir"] == "D1"
    assert _schema.load_shell(root)["by_id"]["D1"]["frozen"] is True
    assert _schema.load_shell(root)["by_id"]["D2"]["frozen"] is True
    assert read_current_state(root / "D1" / "session-state.md") == "Delivered"
    assert read_current_state(root / "D2" / "session-state.md") == "Frozen"
    binding = _binding.load_node_binding(root)
    assert binding["state"] == "reopen_pending"

    permit["state"] = "consumed"
    permit_path.write_text(json.dumps(permit), encoding="utf-8")
    write_session_state(root / "D1" / "session-state.md", "InProgress")
    completed = _ctrl.complete_reopen(
        root,
        binding_id=result["binding_id"],
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )

    assert completed["binding_state"] == "bound"
    assert _schema.load_shell(root)["by_id"]["D1"]["frozen"] is False
    assert _schema.load_shell(root)["by_id"]["D2"]["frozen"] is True
    assert _binding.load_node_binding(root)["permit_state"] == "consumed"
