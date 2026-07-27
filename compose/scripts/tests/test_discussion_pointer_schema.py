#!/usr/bin/env python3
"""Tests for discussion_pointer_schema.py (multi-subdesign v1.1)."""

from __future__ import annotations

import json
from pathlib import Path

import bootstrap  # noqa: F401
import pytest

from dependency_tree_schema import build_tree, save_dependency_tree  # noqa: E402
from discussion_pointer_schema import (  # noqa: E402
    DISCUSSION_POINTER_FILENAME,
    build_pointer_from_tree,
    can_admit,
    can_enter_evaluate,
    load_discussion_pointer,
    ready_ids,
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
    assert ptr == {
        "tree_ref": {"path": "dependency-tree.json", "version": 1},
        "focus": "L1",
        "by_id": {
            "L1": {"intake": "pending", "acceptance": "pending"},
            "L2": {"intake": "pending", "acceptance": "pending"},
        },
    }


def test_validate_ok() -> None:
    tree = _locked_tree()
    ptr = build_pointer_from_tree(tree)
    assert validate_discussion_pointer(ptr, tree) == []


def test_reject_v1_legacy_keys() -> None:
    tree = _locked_tree()
    raw = {
        "tree_ref": {"path": "dependency-tree.json", "version": 1},
        "phase": "intake",
        "pointer": "L2",
        "frontier": "L2",
        "focus": "L2",
        "by_id": {
            "L1": {"intake": "done", "acceptance": "pending"},
            "L2": {"intake": "pending", "acceptance": "pending"},
        },
    }
    errors = validate_discussion_pointer(raw, tree)
    assert any("v1.0 keys forbidden" in e for e in errors)
    assert any("pointer" in e for e in errors)


def test_enter_policy_and_stage_gate() -> None:
    tree = _locked_tree()
    ptr = build_pointer_from_tree(tree)
    ok, _ = can_admit(tree, ptr, "L1")
    assert ok is True
    ok2, reason = can_admit(tree, ptr, "L2")
    assert ok2 is False
    assert reason and "intake" in reason
    assert ready_ids(tree, ptr) == ["L1"]

    ptr["by_id"]["L1"]["intake"] = "done"
    ok3, _ = can_admit(tree, ptr, "L2")
    assert ok3 is True
    ok4, reason4 = can_enter_evaluate(tree, ptr, "L2")
    assert ok4 is False
    assert reason4 and "acceptance" in reason4
    ptr["by_id"]["L1"]["acceptance"] = "done"
    ok5, _ = can_enter_evaluate(tree, ptr, "L2")
    assert ok5 is True


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


def test_load_rejects_legacy_on_disk(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    tree = _locked_tree()
    save_dependency_tree(rev, tree)
    path = rev / DISCUSSION_POINTER_FILENAME
    path.write_text(
        json.dumps(
            {
                "tree_ref": {"path": "dependency-tree.json", "version": 1},
                "phase": "intake",
                "pointer": "L1",
                "frontier": "L1",
                "by_id": {
                    "L1": {"intake": "pending", "acceptance": "pending"},
                    "L2": {"intake": "pending", "acceptance": "pending"},
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="v1.0 keys forbidden"):
        load_discussion_pointer(rev)
