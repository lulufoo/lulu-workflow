#!/usr/bin/env python3
"""Tests for discussion_pointer_schema.py (multi-subdesign MVP)."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401

from dependency_tree_schema import build_tree, save_dependency_tree  # noqa: E402
from discussion_pointer_schema import (  # noqa: E402
    DISCUSSION_POINTER_FILENAME,
    build_pointer_from_tree,
    load_discussion_pointer,
    save_discussion_pointer,
    validate_discussion_pointer,
)


def _locked_tree() -> dict:
    return build_tree(
        nodes=[
            {"id": "L1", "title": "Base", "summary": "a"},
            {"id": "L2", "title": "Dep", "summary": "b"},
        ],
        edges=[{"from": "L2", "to": "L1"}],
        order=["L1", "L2"],
        status="locked",
    )


def test_build_pointer_from_tree() -> None:
    ptr = build_pointer_from_tree(_locked_tree())
    assert ptr["phase"] == "inductive"
    assert ptr["pointer"] == "L1"
    assert ptr["frontier"] == "L1"
    assert ptr["by_id"]["L1"] == {"inductive": "pending", "production": "pending"}
    assert ptr["by_id"]["L2"]["inductive"] == "pending"
    assert ptr["tree_ref"]["path"] == "dependency-tree.json"
    assert ptr["tree_ref"]["version"] == 1


def test_validate_ok() -> None:
    tree = _locked_tree()
    ptr = build_pointer_from_tree(tree)
    assert validate_discussion_pointer(ptr, tree) == []


def test_validate_rejects_pointer_past_frontier() -> None:
    tree = _locked_tree()
    ptr = build_pointer_from_tree(tree)
    ptr["pointer"] = "L2"
    ptr["frontier"] = "L1"
    errors = validate_discussion_pointer(ptr, tree)
    assert any("frontier" in e for e in errors)


def test_roundtrip_io(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    tree = _locked_tree()
    save_dependency_tree(rev, tree)
    ptr = build_pointer_from_tree(tree)
    path = save_discussion_pointer(rev, ptr)
    assert path.name == DISCUSSION_POINTER_FILENAME
    loaded = load_discussion_pointer(rev)
    assert loaded == ptr
