#!/usr/bin/env python3
"""Tests for approach outer shell (archive-1.0 P2.shell)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_SCHEMA = _SCRIPTS / "schema"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_schema = _load("approach_shell_schema", _SCHEMA / "approach_shell_schema.py")
_layout = _load("approach_layout", _SCRIPTS / "approach_layout.py")

# control imports siblings via sys.path; load after schema/layout are importable
import sys

sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_SCHEMA))
_ctrl = _load("approach_shell_control", _SCRIPTS / "approach_shell_control.py")

init_shell = _ctrl.init_shell
enter_split = _ctrl.enter_split
enter_working = _ctrl.enter_working
enter_package_ready = _ctrl.enter_package_ready
set_focus = _ctrl.set_focus
mark_node_delivered = _ctrl.mark_node_delivered
mark_split_delivered = _ctrl.mark_split_delivered
confirm_seal = _ctrl.confirm_seal
load_shell = _schema.load_shell
main_session_dir = _layout.main_session_dir


def _write_delivered(session_dir: Path) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session-state.md").write_text(
        "---\nversion: 1\ncurrent_state: Delivered\nupdated_at: 2026-07-29T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )


def _write_in_progress(session_dir: Path) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "session-state.md").write_text(
        "---\nversion: 1\ncurrent_state: InProgress\nupdated_at: 2026-07-29T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )


def test_init_shell_starts_main(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    shell = init_shell(root)
    assert shell["macro_state"] == "Main"
    assert shell["focus"] is None
    assert shell["by_id"] == {}
    loaded = load_shell(root)
    assert loaded["macro_state"] == "Main"
    assert (root / "main").is_dir()
    assert (root / "discussion-pointer.json").is_file()


def test_main_to_split_requires_main_delivered(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    with pytest.raises(ValueError, match="main is not Delivered"):
        enter_split(root)
    _write_delivered(main_session_dir(root))
    shell = enter_split(root)
    assert shell["macro_state"] == "Split"
    assert shell["split_delivered"] is False


def test_main_to_package_ready_no_split(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    with pytest.raises(ValueError, match="main is not Delivered"):
        enter_package_ready(root)
    _write_delivered(main_session_dir(root))
    shell = enter_package_ready(root)
    assert shell["macro_state"] == "PackageReady"
    assert confirm_seal(root, confirm=True)["sealed"] is True
    with pytest.raises(ValueError, match="human --confirm required"):
        confirm_seal(root, confirm=False)


def test_split_working_package_ready_path(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)
    with pytest.raises(ValueError, match="Split is not Delivered"):
        enter_working(root, ["D1", "D2"])
    mark_split_delivered(root)
    shell = enter_working(root, ["D1", "D2"], focus="D1")
    assert shell["macro_state"] == "Working"
    assert shell["focus"] == "D1"
    assert shell["by_id"]["D1"]["phase"] == "in_progress"
    assert shell["by_id"]["D2"]["phase"] == "pending"
    # S3=B: only focused Dx/ exists after enter_working
    assert (root / "D1").is_dir()
    assert not (root / "D2").exists()

    with pytest.raises(ValueError, match="not all children Delivered"):
        enter_package_ready(root)

    mark_node_delivered(root, "D1")
    mark_node_delivered(root, "D2")
    shell = enter_package_ready(root)
    assert shell["macro_state"] == "PackageReady"


def test_reject_mid_working_focus_switch(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)
    mark_split_delivered(root)
    enter_working(root, ["D1", "D2"], focus="D1")

    with pytest.raises(ValueError, match="not Delivered"):
        set_focus(root, "D2")

    # same focus is a no-op
    shell = set_focus(root, "D1")
    assert shell["focus"] == "D1"

    mark_node_delivered(root, "D1")
    shell = set_focus(root, "D2")
    assert shell["focus"] == "D2"
    assert shell["by_id"]["D2"]["phase"] == "in_progress"


def test_focus_switch_via_session_state_delivered_stub(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)
    mark_split_delivered(root)
    enter_working(root, ["D1", "D2"], focus="D1")
    _write_in_progress(root / "D1")
    with pytest.raises(ValueError, match="not Delivered"):
        set_focus(root, "D2")
    _write_delivered(root / "D1")
    shell = set_focus(root, "D2")
    assert shell["focus"] == "D2"


def test_cannot_enter_split_from_working(tmp_path: Path) -> None:
    root = tmp_path / "lulu-approach"
    init_shell(root)
    _write_delivered(main_session_dir(root))
    enter_split(root)
    mark_split_delivered(root)
    enter_working(root, ["D1"], focus="D1")
    with pytest.raises(ValueError, match="enter_split requires macro_state=Main"):
        enter_split(root)
