#!/usr/bin/env python3
"""Tests for approach freeze-cascade / bind-check-frozen / clear-frozen."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_SCHEMA = _SCRIPTS / "schema"
_WORKFLOW_SCRIPTS = _SCRIPTS.parents[1] / "scripts"
_DECISION_SCRIPTS = _SCRIPTS.parents[1] / "decision" / "scripts"


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

for _p in (_SCRIPTS, _SCHEMA, _WORKFLOW_SCRIPTS, _DECISION_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
_ctrl = _load("approach_shell_control", _SCRIPTS / "approach_shell_control.py")

init_shell = _ctrl.init_shell
enter_split = _ctrl.enter_split
enter_working = _ctrl.enter_working
enter_package_ready = _ctrl.enter_package_ready
commit_focus = _ctrl.commit_focus
mark_node_delivered = _ctrl.mark_node_delivered
mark_split_delivered = _ctrl.mark_split_delivered
freeze_cascade = _ctrl.freeze_cascade
bind_check_frozen = _ctrl.bind_check_frozen
clear_frozen = _ctrl.clear_frozen
confirm_seal = _ctrl.confirm_seal
load_shell = _schema.load_shell
main_session_dir = _layout.main_session_dir
build_tree = _tree.build_tree
save_dependency_tree = _tree.save_dependency_tree


def _write_delivered(session_dir: Path) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session-state.md").write_text(
        "---\nversion: 1\ncurrent_state: Delivered\nupdated_at: 2026-07-30T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )


def _write_frozen(session_dir: Path) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session-state.md").write_text(
        "---\nversion: 1\ncurrent_state: Frozen\nupdated_at: 2026-07-30T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )


def _session_state(session_dir: Path) -> str | None:
    path = session_dir / "session-state.md"
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("current_state:"):
            return line.split(":", 1)[1].strip()
    return None


def _working_chain(tmp_path: Path) -> Path:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)
    mark_split_delivered(root)
    enter_working(root, ["D1", "D2", "D3"], focus="D1")
    tree = build_tree(
        nodes=[
            {"id": "D1", "title": "one", "summary": "s1"},
            {"id": "D2", "title": "two", "summary": "s2"},
            {"id": "D3", "title": "three", "summary": "s3"},
        ],
        edges=[{"from": "D2", "to": "D1"}, {"from": "D3", "to": "D2"}],
        order=["D1", "D2", "D3"],
        status="locked",
    )
    save_dependency_tree(root, tree)
    return root


def test_freeze_cascade_shell_and_session(tmp_path: Path) -> None:
    root = _working_chain(tmp_path)
    mark_node_delivered(root, "D1")
    commit_focus(root, "D2")
    mark_node_delivered(root, "D2")
    commit_focus(root, "D3")
    _write_delivered(root / "D1")
    _write_delivered(root / "D2")
    # D3 dir exists from focus; no session-state → shell_only for D3

    result = freeze_cascade(root, "D1")
    assert result["frozen_ids"] == ["D1", "D2", "D3"]
    assert "D1" in result["session_frozen"]
    assert "D2" in result["session_frozen"]
    shell = load_shell(root)
    assert shell["by_id"]["D1"]["frozen"] is True
    assert shell["by_id"]["D2"]["frozen"] is True
    assert shell["by_id"]["D3"]["frozen"] is True
    assert shell["by_id"]["D1"]["delivered"] is True
    assert _session_state(root / "D1") == "Frozen"
    assert _session_state(root / "D2") == "Frozen"


def test_freeze_cascade_requires_locked_tree(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)
    mark_split_delivered(root)
    enter_working(root, ["D1"], focus="D1")
    with pytest.raises(ValueError, match="missing dependency tree"):
        freeze_cascade(root, "D1")
    tree = build_tree(
        nodes=[{"id": "D1", "title": "one", "summary": "s"}],
        edges=[],
        order=["D1"],
        status="draft",
    )
    save_dependency_tree(root, tree)
    with pytest.raises(ValueError, match="must be locked"):
        freeze_cascade(root, "D1")


def test_commit_focus_allows_frozen_target(tmp_path: Path) -> None:
    root = _working_chain(tmp_path)
    mark_node_delivered(root, "D1")
    commit_focus(root, "D2")
    mark_node_delivered(root, "D2")
    freeze_cascade(root, "D2")
    # D1 still effectively not delivered (frozen after cascade includes D1?
    # freeze D2 → D2,D3 only; D1 not frozen
    shell = commit_focus(root, "D2")
    assert shell["focus"] == "D2"
    assert shell["by_id"]["D2"]["frozen"] is True


def test_bind_check_keeps_frozen_clear_unfreezes(tmp_path: Path) -> None:
    root = _working_chain(tmp_path)
    mark_node_delivered(root, "D1")
    commit_focus(root, "D2")
    _write_delivered(root / "D2")
    freeze_cascade(root, "D2")
    check = bind_check_frozen(root, "D2")
    assert check["realign_required"] is True
    assert check["cleared"] is False
    assert load_shell(root)["by_id"]["D2"]["frozen"] is True
    assert _session_state(root / "D2") == "Frozen"

    cleared = clear_frozen(root, "D2")
    assert cleared["shell_frozen"] is False
    assert load_shell(root)["by_id"]["D2"]["frozen"] is False
    assert load_shell(root)["by_id"]["D3"]["frozen"] is True
    assert _session_state(root / "D2") == "InProgress"

    check2 = bind_check_frozen(root, "D2")
    assert check2["realign_required"] is False


def test_package_ready_blocked_when_frozen(tmp_path: Path) -> None:
    root = _working_chain(tmp_path)
    mark_node_delivered(root, "D1")
    mark_node_delivered(root, "D2")
    mark_node_delivered(root, "D3")
    freeze_cascade(root, "D2")
    with pytest.raises(ValueError, match="frozen nodes present"):
        enter_package_ready(root)


def test_confirm_seal_blocked_when_frozen(tmp_path: Path) -> None:
    root = _working_chain(tmp_path)
    mark_node_delivered(root, "D1")
    mark_node_delivered(root, "D2")
    mark_node_delivered(root, "D3")
    # enter package ready first, then simulate frozen leftover
    shell = enter_package_ready(root)
    assert shell["macro_state"] == "PackageReady"
    data = load_shell(root)
    data["by_id"]["D2"]["frozen"] = True
    _schema.save_shell(root, data)
    with pytest.raises(ValueError, match="frozen nodes present"):
        confirm_seal(
            root,
            confirm=True,
            cycle_id="cyc-freeze-test",
            project_root=tmp_path,
        )


def test_is_node_delivered_false_when_frozen(tmp_path: Path) -> None:
    root = _working_chain(tmp_path)
    mark_node_delivered(root, "D1")
    freeze_cascade(root, "D1")
    assert _ctrl.is_node_delivered(root, "D1") is False
