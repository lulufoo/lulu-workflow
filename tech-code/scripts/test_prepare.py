#!/usr/bin/env python3
"""Tests for tech-code prepare.py."""

import json
from pathlib import Path

from prepare import build_worktree_paths, write_workspace, _read_work_order_round  # noqa: E402


def test_build_worktree_paths_returns_expected_values():
    git_cfg = {
        "worktree_base": ".cache/worktrees",
        "branch_pattern": "wt/{type}-{slug}",
        "default_type": "feat",
    }
    paths = build_worktree_paths("abc12345-dead", git_cfg)
    assert paths["worktree_dir"] == ".cache/worktrees/abc12345-dead/"
    assert paths["branch"] == "wt/feat-abc12345-dead"


def test_read_work_order_round_prefers_active_doc(tmp_path: Path):
    session_state = tmp_path / "session-state.md"
    session_state.write_text(
        "---\nactive_doc: 3\nactive_session: 9\n---\n",
        encoding="utf-8",
    )
    assert _read_work_order_round(session_state) == "3"


def test_read_work_order_round_fallback_to_active_session(tmp_path: Path):
    session_state = tmp_path / "session-state.md"
    session_state.write_text(
        "---\nactive_session: 2\n---\n",
        encoding="utf-8",
    )
    assert _read_work_order_round(session_state) == "2"


def test_write_workspace_writes_absolute_paths(tmp_path: Path):
    cycle_dir = tmp_path / ".cache" / "copilot" / "lulu-dev-workflow" / "fid-123"
    session_dir = cycle_dir / "tech" / "code" / "s1"
    session_dir.mkdir(parents=True, exist_ok=True)
    project_root = tmp_path

    paths = {"worktree_dir": ".cache/worktrees/slug-1/", "branch": "wt/feat-slug-1"}
    tasks = [
        {"task_id": "t1", "target_repo": "repo-a", "task_worktree": "primary"},
        {"task_id": "t2", "target_repo": "repo-b", "task_worktree": ".cache/worktrees/repo-b"},
    ]

    workspace_path = write_workspace(cycle_dir, 1, "slug-1", paths, tasks, project_root)
    payload = json.loads(workspace_path.read_text(encoding="utf-8"))

    assert payload["worktree_path"].startswith(str(project_root.resolve()))
    assert payload["worktree_path"].endswith("/")
    assert payload["project_root"] == str(project_root.resolve())
    assert payload["extra_worktrees"]["repo-b"]["path"].startswith(str(project_root.resolve()))
    assert payload["extra_worktrees"]["repo-b"]["path"].endswith("/")
