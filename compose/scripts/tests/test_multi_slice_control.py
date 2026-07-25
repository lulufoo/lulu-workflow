#!/usr/bin/env python3
"""Tests for multi_slice_control.py."""

from __future__ import annotations

import json
from pathlib import Path

import bootstrap  # noqa: F401

from discussion_pointer_schema import load_discussion_pointer  # noqa: E402
from dependency_tree_schema import load_dependency_tree  # noqa: E402
from multi_slice_control import (  # noqa: E402
    cmd_check_root_facts,
    cmd_lock_tree,
    cmd_migrate_root_facts,
)


def test_check_root_facts_rejects(tmp_path: Path, capsys) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    (rev / "_facts.json").write_text("[]\n", encoding="utf-8")
    assert cmd_check_root_facts(rev) == 1


def test_migrate_then_lock_single_l1(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    (rev / "_facts.json").write_text("[]\n", encoding="utf-8")
    assert cmd_migrate_root_facts(rev, confirm=True) == 0
    assert not (rev / "_facts.json").exists()
    assert (rev / "L1" / "_facts.json").is_file()

    tree = {
        "version": 1,
        "nodes": [{"id": "L1", "title": "Only", "summary": "single"}],
        "edges": [],
        "order": ["L1"],
    }
    assert (
        cmd_lock_tree(
            rev,
            tree_json=json.dumps(tree),
            tree_file=None,
            confirm=True,
        )
        == 0
    )
    locked = load_dependency_tree(rev)
    assert locked["status"] == "locked"
    ptr = load_discussion_pointer(rev)
    assert ptr["pointer"] == "L1"
    assert (rev / "L1").is_dir()


def test_assemble_index_after_production(tmp_path: Path) -> None:
    from discussion_pointer_control import (  # noqa: E402
        cmd_mark_done,
        cmd_phase_switch,
    )
    from multi_slice_control import cmd_assemble_index  # noqa: E402

    rev = tmp_path / "revision1"
    rev.mkdir()
    tree = {
        "version": 1,
        "nodes": [{"id": "L1", "title": "Only", "summary": "single"}],
        "edges": [],
        "order": ["L1"],
    }
    assert (
        cmd_lock_tree(rev, tree_json=json.dumps(tree), tree_file=None, confirm=True)
        == 0
    )
    assert cmd_mark_done(rev, confirm=True) == 0
    assert cmd_phase_switch(rev, confirm=True) == 0
    doc = rev / "L1" / "design-doc.md"
    doc.write_text("# L1\n\n## Boundary\n\n", encoding="utf-8")
    assert cmd_mark_done(rev, confirm=True) == 0
    assert cmd_assemble_index(rev, confirm=True) == 0
    assert (rev / "design-index.md").is_file()
    text = (rev / "design-index.md").read_text(encoding="utf-8")
    assert "L1/design-doc.md" in text


def test_lock_tree_rejects_second_lock(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    tree = {
        "version": 1,
        "nodes": [{"id": "L1", "title": "Only", "summary": "single"}],
        "edges": [],
        "order": ["L1"],
    }
    assert (
        cmd_lock_tree(rev, tree_json=json.dumps(tree), tree_file=None, confirm=True)
        == 0
    )
    assert (
        cmd_lock_tree(rev, tree_json=json.dumps(tree), tree_file=None, confirm=True)
        == 1
    )
