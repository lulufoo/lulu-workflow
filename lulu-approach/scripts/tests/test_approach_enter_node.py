#!/usr/bin/env python3
"""Tests for the public approach node-entry binding protocol."""

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
_layout = _load("approach_layout", _SCRIPTS / "approach_layout.py")
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
from dec_session_state_schema import write_session_state  # noqa: E402
from platforms.paths import cache_dir as platform_cache_dir  # noqa: E402
from platform_schema import detect_platform  # noqa: E402


def _full_template() -> str:
    return (
        "# Decision: {title}\n\n"
        "## 1. User Prior\n\n- placeholder\n\n"
        "## 2. Problem Definition\n\nTBD\n\n"
        "## 3. Direction Readiness\n\nTBD\n\n## 4. Direction Comparison\n\nTBD\n\n"
        "## 5. Settled Direction\n\n"
        "### Decision Rationale\n\nTBD\n\n"
        "### Scope\n\n"
        "**Applies to:** TBD\n\n"
        "**Explicitly excludes:** TBD\n\n"
        "### Landing Approach\n\nTBD\n\n"
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


def _working_approach(project_root: Path, cycle_id: str) -> Path:
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


def test_enter_node_initializes_new_dx_and_binds_active(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-enter-node-001"
    root = _working_approach(project_root, cycle_id)

    result = _ctrl.enter_node(
        root,
        "D1",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )

    assert result["initialized"] is True
    assert result["binding_id"].startswith("bind-")
    assert result["shell"]["focus"] == "D1"
    assert load_active_session(root)["session_dir"] == "D1"
    assert result["context_docs"]["main_decision"] == (root / "main" / "decision-doc.md").as_posix()
    assert result["context_docs"]["boundary_rules"] == (
        _SCRIPTS.parent / "references" / "boundary-rules.md"
    ).resolve().as_posix()
    binding = _binding.load_node_binding(root)
    assert binding["state"] == "bound"
    assert Path(binding["context_snapshot"]["path"]).is_file()


def test_enter_node_rebinds_existing_dx_with_new_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-enter-node-002"
    root = _working_approach(project_root, cycle_id)

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
    result = _ctrl.enter_node(
        root,
        "D2",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )

    assert result["initialized"] is False
    assert result["shell"]["focus"] == "D2"
    assert load_active_session(root)["session_dir"] == "D2"
    assert Path(result["context_snapshot"]["path"]).is_file()


def test_set_focus_is_retired_before_shell_mutation(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    _ctrl.init_shell(root)
    with pytest.raises(ValueError, match="retired.*enter-node"):
        _ctrl.set_focus(root, "D1")
    assert _schema.load_shell(root)["focus"] is None


def test_recover_binding_commit_focus_after_decision_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-enter-node-recover-001"
    root = _working_approach(project_root, cycle_id)

    _ctrl.enter_node(
        root,
        "D1",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )
    _ctrl.mark_node_delivered(root, "D1")
    write_session_state(root / "D1" / "session-state.md", "Delivered")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("simulated focus commit failure")

    monkeypatch.setattr(_ctrl, "commit_focus", _boom)
    with pytest.raises(RuntimeError, match="simulated focus commit failure"):
        _ctrl.enter_node(
            root,
            "D2",
            project_root=project_root,
            cycle_id=cycle_id,
            constraints_path=_CONSTRAINTS,
        )

    binding = _binding.load_node_binding(root)
    assert binding["state"] == "decision_bound"
    assert binding["target"]["node_id"] == "D2"
    assert load_active_session(root)["session_dir"] == "D2"
    assert _schema.load_shell(root)["focus"] == "D1"

    with pytest.raises(ValueError, match="recover-binding"):
        _ctrl.enter_node(
            root,
            "D2",
            project_root=project_root,
            cycle_id=cycle_id,
            constraints_path=_CONSTRAINTS,
        )

    # recover uses force_commit_focus; the broken commit_focus patch stays irrelevant
    result = _ctrl.recover_binding(
        root,
        action="commit-focus",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )

    assert result["binding_state"] == "bound"
    assert result["shell"]["focus"] == "D2"
    assert _binding.load_node_binding(root)["state"] == "bound"
