#!/usr/bin/env python3
"""Tests for repo-map schema and control."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tc_repo_map_control import _parse_binds, list_candidates, put_map  # noqa: E402
from tc_repo_map_schema import (  # noqa: E402
    load_repo_map,
    missing_binds,
    save_repo_map,
    validate_repo_map,
)


def _init_git(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)


    def test_validate_repo_map_requires_version_and_binds():
        errors = validate_repo_map({})
        assert "missing required field: 'version'" in errors
        assert "missing required field: 'binds'" in errors


def test_missing_binds_skips_custom_path():
    missing = missing_binds(
        {"repo-a": "/a"},
        [
            {"target_repo": "repo-a", "execution_worktree": "feature_worktree"},
            {"target_repo": "repo-b", "execution_worktree": "custom_path"},
            {"target_repo": "repo-c", "execution_worktree": "feature_worktree"},
        ],
    )
    assert missing == ["repo-c"]


def test_list_candidates_includes_root_and_sibling_git(tmp_path: Path):
    parent = tmp_path / "Code"
    workspace = parent / "lulu-workbench-workspace"
    sibling = parent / "lulu-workbench"
    other = parent / "notes"
    _init_git(workspace)
    _init_git(sibling)
    other.mkdir(parents=True)

    names = {item["name"] for item in list_candidates(workspace)}
    paths = {item["path"] for item in list_candidates(workspace)}
    assert names == {"lulu-workbench-workspace", "lulu-workbench"}
    assert str(workspace.resolve()) in paths
    assert str(sibling.resolve()) in paths
    assert str(other.resolve()) not in paths


def test_put_map_rejects_checkout_outside_candidates(tmp_path: Path):
    workspace = tmp_path / "workspace"
    _init_git(workspace)
    cycle_dir = tmp_path / "cycle"
    session = cycle_dir / "lulu-exec" / "s1"
    session.mkdir(parents=True)
    (cycle_dir / "lulu-exec" / "session-state.md").write_text(
        "---\nversion: 1\nactive_session: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="not a listed candidate"):
        put_map(cycle_dir, workspace, {"lulu-workbench": str(tmp_path / "missing")})


def test_put_map_writes_binds(tmp_path: Path):
    parent = tmp_path / "Code"
    workspace = parent / "lulu-workbench-workspace"
    sibling = parent / "lulu-workbench"
    _init_git(workspace)
    _init_git(sibling)
    cycle_dir = tmp_path / "cycle"
    session = cycle_dir / "lulu-exec" / "s1"
    session.mkdir(parents=True)
    (cycle_dir / "lulu-exec" / "session-state.md").write_text(
        "---\nversion: 1\nactive_session: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    payload = put_map(cycle_dir, workspace, {"lulu-workbench": str(sibling.resolve())})
    assert payload["ok"] is True
    binds = load_repo_map(session / "repo-map.json")
    assert binds["lulu-workbench"] == str(sibling.resolve())


def test_put_map_accepts_empty_binds_when_no_task_binds_a_repo(tmp_path: Path):
    workspace = tmp_path / "workspace"
    _init_git(workspace)
    cycle_dir = tmp_path / "cycle"
    session = cycle_dir / "lulu-exec" / "s1"
    session.mkdir(parents=True)
    (cycle_dir / "lulu-exec" / "session-state.md").write_text(
        "---\nversion: 1\nactive_session: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    assert _parse_binds("{}") == {}
    payload = put_map(cycle_dir, workspace, {})
    assert payload["binds"] == {}
    assert load_repo_map(session / "repo-map.json") == {}


def test_save_and_load_roundtrip(tmp_path: Path):
    dest = tmp_path / "repo-map.json"
    save_repo_map(dest, {"repo-a": "/abs/repo-a"})
    assert json.loads(dest.read_text(encoding="utf-8"))["version"] == 1
    assert load_repo_map(dest) == {"repo-a": "/abs/repo-a"}
