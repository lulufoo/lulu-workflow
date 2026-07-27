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
            rulers_json=None,
            rulers_file=None,
            confirm=True,
        )
        == 0
    )
    locked = load_dependency_tree(rev)
    assert locked["status"] == "locked"
    ptr = load_discussion_pointer(rev)
    assert ptr["focus"] == "L1"
    assert set(ptr) == {"tree_ref", "focus", "by_id"}
    assert (rev / "L1").is_dir()


def test_assemble_index_after_production(tmp_path: Path) -> None:
    from discussion_pointer_control import cmd_mark_done  # noqa: E402
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
        cmd_lock_tree(
            rev,
            tree_json=json.dumps(tree),
            tree_file=None,
            rulers_json=None,
            rulers_file=None,
            confirm=True,
        )
        == 0
    )
    from discussion_pointer_schema import (  # noqa: E402
        load_discussion_pointer,
        save_discussion_pointer,
    )

    profile_id = "lulu-design"
    assert cmd_mark_done(
        rev, confirm=True, kind="intake", profile_id=profile_id
    ) == 0
    doc = rev / "L1" / "design-doc.md"
    doc.write_text("# L1\n\n## Boundary\n\n", encoding="utf-8")
    ptr = load_discussion_pointer(rev)
    ptr["by_id"]["L1"]["phase"] = "evaluating"
    save_discussion_pointer(rev, ptr)
    assert cmd_mark_done(
        rev, confirm=True, kind="acceptance", profile_id=profile_id
    ) == 0
    assert cmd_assemble_index(rev, confirm=True, profile_id=profile_id) == 0
    assert (rev / "design-index.md").is_file()
    text = (rev / "design-index.md").read_text(encoding="utf-8")
    assert "L1/design-doc.md" in text


def test_assemble_index_uses_plan_doc_filename(tmp_path: Path) -> None:
    from discussion_pointer_control import cmd_mark_done  # noqa: E402
    from discussion_pointer_schema import (  # noqa: E402
        load_discussion_pointer,
        save_discussion_pointer,
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
        cmd_lock_tree(
            rev,
            tree_json=json.dumps(tree),
            tree_file=None,
            rulers_json=None,
            rulers_file=None,
            confirm=True,
        )
        == 0
    )
    profile_id = "lulu-plan"
    assert cmd_mark_done(
        rev, confirm=True, kind="intake", profile_id=profile_id
    ) == 0
    doc = rev / "L1" / "tech-doc.md"
    doc.write_text("# L1\n\n## Boundary\n\n", encoding="utf-8")
    ptr = load_discussion_pointer(rev)
    ptr["by_id"]["L1"]["phase"] = "evaluating"
    save_discussion_pointer(rev, ptr)
    assert cmd_mark_done(
        rev, confirm=True, kind="acceptance", profile_id=profile_id
    ) == 0
    assert cmd_assemble_index(rev, confirm=True, profile_id=profile_id) == 0
    assert (rev / "tech-index.md").is_file()
    text = (rev / "tech-index.md").read_text(encoding="utf-8")
    assert "L1/tech-doc.md" in text
    assert "# Tech Index" in text


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
        cmd_lock_tree(
            rev,
            tree_json=json.dumps(tree),
            tree_file=None,
            rulers_json=None,
            rulers_file=None,
            confirm=True,
        )
        == 0
    )
    assert (
        cmd_lock_tree(
            rev,
            tree_json=json.dumps(tree),
            tree_file=None,
            rulers_json=None,
            rulers_file=None,
            confirm=True,
        )
        == 1
    )


def _sample_rulers() -> dict:
    return {
        "version": 1,
        "cut_axis": "tech_domain",
        "rulers": {
            "L1": {
                "id": "L1",
                "job": "Core API",
                "in": ["API surface"],
                "out": ["UI"],
                "seam": [
                    {
                        "with": "L2",
                        "owns": "full_plan",
                        "note": "L1 owns contract shape",
                    }
                ],
                "plan_checklist": ["endpoints listed"],
            },
            "L2": {
                "id": "L2",
                "job": "UI client",
                "in": ["screens"],
                "out": ["API impl"],
                "seam": [
                    {
                        "with": "L1",
                        "owns": "depend_only",
                        "note": "depends on L1 contract",
                    }
                ],
                "plan_checklist": ["screens mapped"],
            },
        },
    }


def test_multi_l_lock_requires_rulers(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    tree = {
        "version": 1,
        "nodes": [
            {"id": "L1", "title": "A", "summary": "a"},
            {"id": "L2", "title": "B", "summary": "b"},
        ],
        "edges": [{"from": "L2", "to": "L1"}],
        "order": ["L1", "L2"],
    }
    assert (
        cmd_lock_tree(
            rev,
            tree_json=json.dumps(tree),
            tree_file=None,
            rulers_json=None,
            rulers_file=None,
            confirm=True,
        )
        == 1
    )


def test_multi_l_lock_with_rulers_and_check_ready(tmp_path: Path) -> None:
    from multi_slice_control import cmd_check_split_ready  # noqa: E402
    from slice_rulers_schema import load_slice_rulers  # noqa: E402

    rev = tmp_path / "revision1"
    rev.mkdir()
    tree = {
        "version": 1,
        "nodes": [
            {"id": "L1", "title": "A", "summary": "a"},
            {"id": "L2", "title": "B", "summary": "b"},
        ],
        "edges": [{"from": "L2", "to": "L1"}],
        "order": ["L1", "L2"],
    }
    assert (
        cmd_lock_tree(
            rev,
            tree_json=json.dumps(tree),
            tree_file=None,
            rulers_json=json.dumps(_sample_rulers()),
            rulers_file=None,
            confirm=True,
        )
        == 0
    )
    rulers = load_slice_rulers(rev)
    assert rulers["status"] == "locked"
    assert rulers["cut_axis"] == "tech_domain"
    assert cmd_check_split_ready(rev) == 0


def test_dual_full_plan_seam_rejected(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    tree = {
        "version": 1,
        "nodes": [
            {"id": "L1", "title": "A", "summary": "a"},
            {"id": "L2", "title": "B", "summary": "b"},
        ],
        "edges": [{"from": "L2", "to": "L1"}],
        "order": ["L1", "L2"],
    }
    bad = _sample_rulers()
    bad["rulers"]["L2"]["seam"][0]["owns"] = "full_plan"
    assert (
        cmd_lock_tree(
            rev,
            tree_json=json.dumps(tree),
            tree_file=None,
            rulers_json=json.dumps(bad),
            rulers_file=None,
            confirm=True,
        )
        == 1
    )


def test_intake_complete_requires_slots(tmp_path: Path) -> None:
    from multi_slice_control import (  # noqa: E402
        cmd_complete_intake,
        cmd_write_intake,
    )
    from split_intake_schema import empty_intake  # noqa: E402

    rev = tmp_path / "revision1"
    rev.mkdir()
    draft = empty_intake()
    assert (
        cmd_write_intake(rev, intake_json=json.dumps(draft), intake_file=None) == 0
    )
    assert cmd_complete_intake(rev, confirm=True) == 1
    for key in draft["slots"]:
        draft["slots"][key] = "N/A"
    assert (
        cmd_write_intake(rev, intake_json=json.dumps(draft), intake_file=None) == 0
    )
    assert cmd_complete_intake(rev, confirm=True) == 0
