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
_candidate = _load(
    "approach_split_candidate_schema", _SCHEMA / "approach_split_candidate_schema.py"
)

for _path in (_SCRIPTS, _SCHEMA, _WORKFLOW_SCRIPTS, _DECISION_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
_ctrl = _load("approach_shell_control", _SCRIPTS / "approach_shell_control.py")
_split = _load("approach_split_control", _SCRIPTS / "approach_split_control.py")

from dec_active_session_schema import load_active_session  # noqa: E402
from dec_session_state_schema import read_current_state, write_session_state  # noqa: E402
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
    assert read_current_state(root / "D1" / "session-state.md") == "Completed"
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


def test_reopen_main_freezes_working_nodes_binds_main_and_issues_permit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-main-reopen-001"
    root = _prepared_chain(project_root, cycle_id)

    result = _ctrl.reopen_node(
        root,
        "main",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )

    shell = _schema.load_shell(root)
    assert result["transaction_id"].startswith("mlr-")
    assert shell["macro_state"] == "MainReopen"
    assert shell["focus"] == "main"
    assert all(cell["frozen"] is True for cell in shell["by_id"].values())
    assert load_active_session(root)["session_dir"] == "main"
    assert json.loads(Path(result["permit_path"]).read_text(encoding="utf-8"))["node_id"] == "main"
    assert _binding.load_node_binding(root)["state"] == "reopen_pending"
    transaction = json.loads((root / "mainline-reopen.json").read_text(encoding="utf-8"))
    assert transaction["state"] == "main_reopen_pending"
    assert transaction["target"] == {"kind": "main", "node_id": "main"}


def test_complete_main_reopen_keeps_working_nodes_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-main-reopen-complete-001"
    root = _prepared_chain(project_root, cycle_id)
    result = _ctrl.reopen_node(
        root,
        "main",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )

    permit_path = Path(result["permit_path"])
    permit = json.loads(permit_path.read_text(encoding="utf-8"))
    permit["state"] = "consumed"
    permit_path.write_text(json.dumps(permit), encoding="utf-8")
    write_session_state(root / "main" / "session-state.md", "InProgress")

    completed = _ctrl.complete_main_reopen(
        root,
        transaction_id=result["transaction_id"],
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )

    assert completed["state"] == "main_repaired"
    shell = _schema.load_shell(root)
    assert shell["macro_state"] == "Main"
    assert shell["focus"] == "main"
    assert all(cell["frozen"] is True for cell in shell["by_id"].values())


def test_cli_completes_main_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-main-reopen-cli-001"
    root = _prepared_chain(project_root, cycle_id)
    result = _ctrl.reopen_node(
        root,
        "main",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )
    permit_path = Path(result["permit_path"])
    permit = json.loads(permit_path.read_text(encoding="utf-8"))
    permit["state"] = "consumed"
    permit_path.write_text(json.dumps(permit), encoding="utf-8")
    write_session_state(root / "main" / "session-state.md", "InProgress")

    try:
        rc = _ctrl.main(
            [
                "--approach-root",
                str(root),
                "complete-main-reopen",
                "--transaction-id",
                result["transaction_id"],
                "--project-root",
                str(project_root),
                "--cycle-id",
                cycle_id,
                "--constraints",
                str(_CONSTRAINTS),
            ]
        )
    except SystemExit:
        pytest.fail("complete-main-reopen must be a supported CLI command")

    assert rc == 0


def test_reopen_split_freezes_working_nodes_and_binds_main(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-split-reopen-001"
    root = _prepared_chain(project_root, cycle_id)

    result = _ctrl.reopen_node(
        root,
        "split",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )

    shell = _schema.load_shell(root)
    assert shell["macro_state"] == "SplitReopen"
    assert shell["focus"] == "main"
    assert all(cell["frozen"] is True for cell in shell["by_id"].values())
    assert load_active_session(root)["session_dir"] == "main"
    assert result["transaction_id"].startswith("mlr-")
    transaction = json.loads((root / "mainline-reopen.json").read_text(encoding="utf-8"))
    assert transaction["state"] == "split_pending"
    assert transaction["target"] == {"kind": "split", "node_id": "split"}


def test_enter_split_consumes_mainline_split_pending(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-split-entry-001"
    root = _prepared_chain(project_root, cycle_id)
    _ctrl.reopen_node(
        root,
        "split",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )

    result = _ctrl.enter_node(
        root,
        "split",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )

    assert result["node_id"] == "split"
    assert _schema.load_shell(root)["macro_state"] == "SplitReopen"
    transaction = json.loads((root / "mainline-reopen.json").read_text(encoding="utf-8"))
    assert transaction["state"] == "split_review"


def test_split_review_persists_candidate_and_structural_impact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-split-candidate-001"
    root = _prepared_chain(project_root, cycle_id)
    reopened = _ctrl.reopen_node(
        root,
        "split",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )
    _ctrl.enter_node(
        root,
        "split",
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=_CONSTRAINTS,
    )
    candidate = _candidate.build_candidate(
        nodes=[
            {"id": "C1", "title": "one", "summary": "s1"},
            {"id": "C2", "title": "two", "summary": "s2"},
        ],
        edges=[{"from": "C2", "to": "C1"}],
        order=["C1", "C2"],
        cut_axis="domain_seam",
        rulers={
            "C1": {
                "id": "C1",
                "job": "one",
                "boundary": "one only",
                "deps_summary": "none",
            },
            "C2": {
                "id": "C2",
                "job": "two",
                "boundary": "two only",
                "deps_summary": "depends on C1",
            },
        },
        mapping={
            "C1": {"kind": "existing", "node_id": "D1"},
            "C2": {"kind": "existing", "node_id": "D2"},
        },
    )

    result = _split.write_reopen_candidate(
        root, transaction_id=reopened["transaction_id"], candidate=candidate
    )

    assert Path(result["candidate_path"]).is_file()
    assert result["structure_match"] is True
    transaction = json.loads((root / "mainline-reopen.json").read_text(encoding="utf-8"))
    assert transaction["candidate_id_mapping"] == candidate["mapping"]
    assert transaction["structure_signature"]["old"] == transaction["structure_signature"]["candidate"]

    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    try:
        rc = _split.main(
            [
                "--approach-root",
                str(root),
                "write-reopen-candidate",
                "--transaction-id",
                reopened["transaction_id"],
                "--candidate",
                str(candidate_path),
            ]
        )
    except SystemExit:
        pytest.fail("write-reopen-candidate must be a supported CLI command")
    assert rc == 0

    completed = _ctrl.complete_split_reopen(
        root, transaction_id=reopened["transaction_id"], confirm=True
    )
    assert completed["state"] == "working_retained"
    assert _schema.load_shell(root)["macro_state"] == "SplitReopen"
    assert all(cell["frozen"] is True for cell in _schema.load_shell(root)["by_id"].values())


def test_confirm_changed_split_candidate_archives_and_rebuilds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.chdir(project_root)
    _write_template_config(project_root)
    cycle_id = "feature-split-rebuild-001"
    root = _prepared_chain(project_root, cycle_id)
    reopened = _ctrl.reopen_node(
        root, "split", project_root=project_root, cycle_id=cycle_id, constraints_path=_CONSTRAINTS
    )
    _ctrl.enter_node(
        root, "split", project_root=project_root, cycle_id=cycle_id, constraints_path=_CONSTRAINTS
    )
    candidate = _candidate.build_candidate(
        nodes=[{"id": "C1", "title": "replacement", "summary": "replacement seam"}],
        edges=[],
        order=["C1"],
        cut_axis="replacement",
        rulers={
            "C1": {
                "id": "C1", "job": "replace", "boundary": "replacement",
                "deps_summary": "none",
            }
        },
        mapping={"C1": {"kind": "new", "node_id": "D3"}},
    )
    _split.write_reopen_candidate(root, transaction_id=reopened["transaction_id"], candidate=candidate)

    completed = _ctrl.complete_split_reopen(
        root, transaction_id=reopened["transaction_id"], confirm=True
    )

    assert completed["state"] == "working_rebuilt"
    assert (root / "working-archive" / reopened["transaction_id"] / "dependency-tree.json").is_file()
    assert _schema.load_shell(root)["by_id"] == {"D3": _schema.empty_cell()}

    entered = _ctrl.enter_node(
        root, "D3", project_root=project_root, cycle_id=cycle_id, constraints_path=_CONSTRAINTS
    )
    assert entered["shell"]["macro_state"] == "Working"
    assert entered["shell"]["focus"] == "D3"
