#!/usr/bin/env python3
"""Tests for dependency_tree_schema.py (multi-subdesign MVP)."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401

from dependency_tree_schema import (  # noqa: E402
    DEPENDENCY_TREE_FILENAME,
    build_tree,
    dependency_tree_path,
    load_dependency_tree,
    save_dependency_tree,
    validate_dependency_tree,
)


def _valid_two_node() -> dict:
    return {
        "version": 1,
        "status": "locked",
        "nodes": [
            {"id": "L1", "title": "Base", "summary": "foundation"},
            {"id": "L2", "title": "Dep", "summary": "depends on base"},
        ],
        "edges": [{"from": "L2", "to": "L1"}],
        "order": ["L1", "L2"],
    }


def test_validate_ok() -> None:
    assert validate_dependency_tree(_valid_two_node()) == []


def test_validate_rejects_order_before_dependency() -> None:
    bad = _valid_two_node()
    bad["order"] = ["L2", "L1"]
    errors = validate_dependency_tree(bad)
    assert any("order" in e for e in errors)


def test_validate_rejects_unknown_edge_endpoint() -> None:
    bad = _valid_two_node()
    bad["edges"] = [{"from": "L2", "to": "L9"}]
    errors = validate_dependency_tree(bad)
    assert any("L9" in e for e in errors)


def test_validate_single_l1() -> None:
    tree = build_tree(
        nodes=[{"id": "L1", "title": "Only", "summary": "single"}],
        edges=[],
        order=["L1"],
        status="locked",
    )
    assert validate_dependency_tree(tree) == []
    assert tree["nodes"][0]["id"] == "L1"


def test_validate_rejects_progress_on_node() -> None:
    bad = _valid_two_node()
    bad["nodes"][0]["inductive"] = "done"
    errors = validate_dependency_tree(bad)
    assert any("unexpected" in e for e in errors)


def test_roundtrip_io(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    tree = _valid_two_node()
    path = save_dependency_tree(rev, tree)
    assert path.name == DEPENDENCY_TREE_FILENAME
    loaded = load_dependency_tree(rev)
    assert loaded == tree
    assert dependency_tree_path(rev) == path


def test_load_missing_raises(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    try:
        load_dependency_tree(rev)
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass


def test_build_tree_default_draft() -> None:
    tree = build_tree(
        nodes=[{"id": "L1", "title": "t", "summary": "s"}],
        edges=[],
        order=["L1"],
    )
    assert tree["status"] == "draft"
    assert tree["version"] == 1
