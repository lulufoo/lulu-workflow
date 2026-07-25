#!/usr/bin/env python3
"""Tests for discussion_pointer_control.py (multi-subdesign MVP)."""

from __future__ import annotations

import json
from pathlib import Path

import bootstrap  # noqa: F401
from bootstrap import CORE  # noqa: E402

from dependency_tree_schema import build_tree, save_dependency_tree  # noqa: E402
from discussion_pointer_control import (  # noqa: E402
    cmd_advance,
    cmd_backtrack,
    cmd_mark_done,
    cmd_phase_switch,
    cmd_resume,
    cmd_status,
)
from discussion_pointer_schema import (  # noqa: E402
    build_pointer_from_tree,
    load_discussion_pointer,
    save_discussion_pointer,
)


def _seed_rev(tmp_path: Path) -> Path:
    rev = tmp_path / "revision1"
    rev.mkdir()
    tree = build_tree(
        nodes=[
            {"id": "L1", "title": "Base", "summary": "a"},
            {"id": "L2", "title": "Dep", "summary": "b"},
        ],
        edges=[{"from": "L2", "to": "L1"}],
        order=["L1", "L2"],
        status="locked",
    )
    save_dependency_tree(rev, tree)
    save_discussion_pointer(rev, build_pointer_from_tree(tree))
    return rev


def test_status_ok(tmp_path: Path, capsys) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_status(rev) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["pointer"] == "L1"
    assert out["phase"] == "inductive"


def test_resume_no_state_change(tmp_path: Path, capsys) -> None:
    rev = _seed_rev(tmp_path)
    before = load_discussion_pointer(rev)
    assert cmd_resume(rev) == 0
    after = load_discussion_pointer(rev)
    assert after == before
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["command"] == "resume"


def test_mark_done_and_advance(tmp_path: Path, capsys) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_mark_done(rev, confirm=True) == 0
    assert cmd_advance(rev, confirm=True) == 0
    ptr = load_discussion_pointer(rev)
    assert ptr["pointer"] == "L2"
    assert ptr["frontier"] == "L2"
    assert ptr["by_id"]["L1"]["inductive"] == "done"


def test_advance_without_done_rejected(tmp_path: Path, capsys) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_advance(rev, confirm=True) == 1
    err = json.loads(capsys.readouterr().err)
    assert err["ok"] is False
    ptr = load_discussion_pointer(rev)
    assert ptr["pointer"] == "L1"


def test_advance_without_confirm_rejected(tmp_path: Path, capsys) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_mark_done(rev, confirm=True) == 0
    assert cmd_advance(rev, confirm=False) == 1
    ptr = load_discussion_pointer(rev)
    assert ptr["pointer"] == "L1"


def test_backtrack_keeps_frontier(tmp_path: Path) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_mark_done(rev, confirm=True) == 0
    assert cmd_advance(rev, confirm=True) == 0
    assert cmd_backtrack(rev, target="L1", confirm=True) == 0
    ptr = load_discussion_pointer(rev)
    assert ptr["pointer"] == "L1"
    assert ptr["frontier"] == "L2"
    assert ptr["by_id"]["L1"]["inductive"] == "done"


def test_backtrack_past_frontier_rejected(tmp_path: Path, capsys) -> None:
    rev = _seed_rev(tmp_path)
    # frontier still L1; cannot move pointer to L2 via backtrack (that's forward)
    assert cmd_backtrack(rev, target="L2", confirm=True) == 1
    ptr = load_discussion_pointer(rev)
    assert ptr["pointer"] == "L1"


def test_phase_switch(tmp_path: Path) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_mark_done(rev, confirm=True) == 0
    assert cmd_advance(rev, confirm=True) == 0
    assert cmd_mark_done(rev, confirm=True) == 0
    assert cmd_phase_switch(rev, confirm=True) == 0
    ptr = load_discussion_pointer(rev)
    assert ptr["phase"] == "production"
    assert ptr["pointer"] == "L1"
    assert ptr["frontier"] == "L1"
    assert ptr["by_id"]["L1"]["inductive"] == "done"
    assert ptr["by_id"]["L1"]["production"] == "pending"


def test_phase_switch_incomplete_rejected(tmp_path: Path) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_mark_done(rev, confirm=True) == 0
    assert cmd_phase_switch(rev, confirm=True) == 1
    ptr = load_discussion_pointer(rev)
    assert ptr["phase"] == "inductive"


def test_control_module_lives_in_core() -> None:
    assert (CORE / "discussion_pointer_control.py").is_file()


def test_production_mark_done_requires_boundary(tmp_path: Path) -> None:
    rev = _seed_rev(tmp_path)
    assert cmd_mark_done(rev, confirm=True) == 0
    assert cmd_advance(rev, confirm=True) == 0
    assert cmd_mark_done(rev, confirm=True) == 0
    assert cmd_phase_switch(rev, confirm=True) == 0
    assert cmd_mark_done(rev, confirm=True) == 1
    doc = rev / "L1" / "design-doc.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# L1\n\n## Boundary\n\n", encoding="utf-8")
    assert cmd_mark_done(rev, confirm=True) == 0


def test_seam_report_advisory(tmp_path: Path, capsys) -> None:
    from discussion_pointer_control import cmd_seam_report

    rev = _seed_rev(tmp_path)
    assert cmd_seam_report(rev) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hard_reject"] is False
    assert out["edges_checked"] == 1
