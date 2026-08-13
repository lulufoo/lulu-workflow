#!/usr/bin/env python3
"""Tests for multi-L home_l enforcement on facts write."""

from __future__ import annotations

import json
from pathlib import Path

import bootstrap  # noqa: F401
import pytest

from facts_control import cmd_write  # noqa: E402
from multi_slice_control import cmd_lock_tree  # noqa: E402
from workflow_paths import seed_revision_profile_pointer  # noqa: E402

_REPO = Path(__file__).resolve().parents[4]


def _lock_multi(rev: Path) -> None:
    tree = {
        "version": 1,
        "nodes": [
            {"id": "L1", "title": "A", "summary": "a"},
            {"id": "L2", "title": "B", "summary": "b"},
        ],
        "edges": [{"from": "L2", "to": "L1"}],
        "order": ["L1", "L2"],
    }
    rulers = {
        "version": 1,
        "cut_axis": "tech_domain",
        "rulers": {
            "L1": {
                "id": "L1",
                "job": "Core",
                "in": ["api"],
                "out": ["ui"],
                "seam": [
                    {"with": "L2", "owns": "full_plan", "note": "owns contract"}
                ],
                "plan_checklist": ["api listed"],
            },
            "L2": {
                "id": "L2",
                "job": "UI",
                "in": ["ui"],
                "out": ["api"],
                "seam": [
                    {"with": "L1", "owns": "depend_only", "note": "depends"}
                ],
                "plan_checklist": ["screens"],
            },
        },
    }
    assert (
        cmd_lock_tree(
            rev,
            tree_json=json.dumps(tree),
            tree_file=None,
            rulers_json=json.dumps(rulers),
            rulers_file=None,
            confirm=True,
        )
        == 0
    )


def _args(rev: Path, facts_file: Path, *, target_l: str = "", package_confirm: bool = False):
    return type(
        "A",
        (),
        {
            "revision_dir": rev,
            "facts_file": facts_file,
            "target_l": target_l,
            "package_confirm": package_confirm,
            "project_root": _REPO,
        },
    )()


def test_multi_l_write_rejects_missing_home_l(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    seed_revision_profile_pointer(rev)
    _lock_multi(rev)
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(
        json.dumps(
            [{"id": "F-1", "text": "hello", "lens_tags": ["CTX"]}],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert cmd_write(_args(rev, facts_file, target_l="L1")) == 1


def test_multi_l_write_accepts_home_l(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    seed_revision_profile_pointer(rev)
    _lock_multi(rev)
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(
        json.dumps(
            [
                {
                    "id": "F-1",
                    "text": "hello",
                    "lens_tags": ["CTX"],
                    "home_l": "L1",
                    "home_rationale": "in: api",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert cmd_write(_args(rev, facts_file, target_l="L1")) == 0
    assert (rev / "L1" / "_facts.json").is_file()


def test_package_requires_confirm(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    seed_revision_profile_pointer(rev)
    _lock_multi(rev)
    facts_file = tmp_path / "facts.json"
    facts_file.write_text(
        json.dumps(
            [
                {
                    "id": "F-1",
                    "text": "cross-cutting",
                    "lens_tags": ["CTX"],
                    "home_l": "package",
                    "home_rationale": "human package",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert cmd_write(_args(rev, facts_file, target_l="package")) == 1
    assert (
        cmd_write(
            _args(rev, facts_file, target_l="package", package_confirm=True)
        )
        == 0
    )
    assert (rev / "package" / "_facts.json").is_file()
