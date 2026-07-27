#!/usr/bin/env python3
"""Tests for active_slice_dir + inductive_out_dir pointer wiring."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401

from dependency_tree_schema import build_tree, save_dependency_tree  # noqa: E402
from discussion_pointer_schema import (  # noqa: E402
    active_slice_dir,
    build_pointer_from_tree,
    save_discussion_pointer,
)
from session_state_schema import save_active_doc  # noqa: E402
from workflow_paths import seed_profile_pointer_for_tests  # noqa: E402
from workflow_profile_paths import (  # noqa: E402
    doc_dir,
    inductive_out_dir,
    session_state_path,
)


def test_active_slice_dir_legacy_without_pointer(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    assert active_slice_dir(rev) == rev.resolve()


def test_active_slice_dir_follows_pointer(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    tree = build_tree(
        nodes=[
            {"id": "L1", "title": "a", "summary": "a"},
            {"id": "L2", "title": "b", "summary": "b"},
        ],
        edges=[{"from": "L2", "to": "L1"}],
        order=["L1", "L2"],
        status="locked",
    )
    save_dependency_tree(rev, tree)
    ptr = build_pointer_from_tree(tree)
    ptr["focus"] = "L2"
    ptr["by_id"]["L1"]["intake"] = "done"
    save_discussion_pointer(rev, ptr, tree=tree)
    assert active_slice_dir(rev) == (rev / "L2").resolve()


def test_inductive_out_dir_with_pointer(tmp_path: Path) -> None:
    cycle = "feat-slice-wiring"
    seed_profile_pointer_for_tests(tmp_path, cycle, "lulu-design")
    ss = tmp_path / session_state_path(cycle, "lulu-design", tmp_path)
    save_active_doc(ss, 1)
    rev = tmp_path / doc_dir(cycle, 1, "lulu-design", tmp_path)
    rev.mkdir(parents=True)
    tree = build_tree(
        nodes=[{"id": "L1", "title": "only", "summary": "s"}],
        edges=[],
        order=["L1"],
        status="locked",
    )
    save_dependency_tree(rev, tree)
    save_discussion_pointer(rev, build_pointer_from_tree(tree), tree=tree)

    out = inductive_out_dir(cycle, "lulu-design", tmp_path)
    assert out.as_posix().endswith("revision1/L1")
