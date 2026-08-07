#!/usr/bin/env python3
"""Tests for narrative_arc_draft_schema (archive-9.0)."""

from __future__ import annotations

import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parents[1] / "section"
if str(_SECTION) not in sys.path:
    sys.path.insert(0, str(_SECTION))

from narrative_arc_draft_schema import (  # noqa: E402
    add_leaf_node,
    attach_fact,
    empty_draft,
    move_node,
    rename_leaf,
    save_narrative_arc_draft,
    validate_narrative_arc_draft,
)


def _seed() -> dict:
    d = empty_draft()
    d["tree"] = {
        "id": "root",
        "title": "Root",
        "children": [
            {
                "id": "g1",
                "title": "Group",
                "children": [{"id": "leaf-a", "title": "A", "children": []}],
            }
        ],
    }
    d["leaves"] = [{"id": "leaf-a", "title": "A", "fact_ids": ["F-1"]}]
    d["meta"]["leaf_mounts"] = {"leaf-a": "seed"}
    return d


def test_seed_ok():
    assert validate_narrative_arc_draft(_seed()) == []


def test_chapters_forbidden():
    data = _seed()
    data["leaves"][0]["chapters"] = [{"lens": "I", "fact_ids": ["F-1"]}]
    assert any("chapters" in e for e in validate_narrative_arc_draft(data))


def test_add_node_append_and_index(tmp_path: Path):
    data = add_leaf_node(
        _seed(),
        parent_id="g1",
        leaf_id="leaf-b",
        title="B",
    )
    assert any(leaf["id"] == "leaf-b" for leaf in data["leaves"])
    assert data["meta"]["leaf_mounts"]["leaf-b"] == "add"
    data2 = add_leaf_node(
        data,
        parent_id="g1",
        leaf_id="leaf-c",
        title="C",
        index=0,
    )
    kids = data2["tree"]["children"][0]["children"]
    assert kids[0]["id"] == "leaf-c"


def test_move_and_rename():
    data = add_leaf_node(_seed(), parent_id="g1", leaf_id="leaf-b", title="B")
    moved = move_node(data, node_id="leaf-b", new_parent="root", index=0)
    assert moved["tree"]["children"][0]["id"] == "leaf-b"
    renamed = rename_leaf(moved, leaf_id="leaf-b", title="Bee")
    assert renamed["leaves"][1]["title"] == "Bee"


def test_attach_fact_unique():
    data = attach_fact(_seed(), leaf_id="leaf-a", fact_id="F-2")
    assert "F-2" in data["leaves"][0]["fact_ids"]
    data2 = add_leaf_node(data, parent_id="g1", leaf_id="leaf-b", title="B")
    try:
        attach_fact(data2, leaf_id="leaf-b", fact_id="F-1")
        raise AssertionError("expected duplicate attach to fail")
    except ValueError as exc:
        assert "already attached" in str(exc)


def test_save_roundtrip(tmp_path: Path):
    path = tmp_path / "_narrative-arc.draft.json"
    save_narrative_arc_draft(path, _seed())
    assert path.is_file()
