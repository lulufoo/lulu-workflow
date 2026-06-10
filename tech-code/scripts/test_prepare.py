#!/usr/bin/env python3
"""Tests for tech-code prepare.py."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from prepare import build_worktree_paths, validate_preparing_to_executing, write_workspace  # noqa: E402
from workflow_state_schema import init_preparing, save_workflow_state  # noqa: E402

_SCRIPT = Path(__file__).resolve().parent / "prepare.py"


def test_build_worktree_paths_returns_expected_values():
    git_cfg = {
        "worktree_base": ".cache/worktrees",
        "branch_pattern": "wt/{type}-{slug}",
        "default_type": "feat",
    }
    paths = build_worktree_paths("abc12345-dead", git_cfg)
    assert paths["worktree_dir"] == ".cache/worktrees/abc12345-dead/"
    assert paths["branch"] == "wt/feat-abc12345-dead"


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


def _setup_validate_session(tmp_path: Path) -> tuple[Path, Path]:
    cycle_dir = tmp_path / "cycle-id"
    session_dir = cycle_dir / "tech" / "code" / "s1"
    session_dir.mkdir(parents=True)
    (cycle_dir / "tech" / "code" / "session-state.md").write_text(
        "---\nversion: 1\nactive_session: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    ws_path = session_dir / "workflow-state.md"
    init_preparing(ws_path, mode="work-order", task_list_ref=str(session_dir / "code-task-list.md"))
    (session_dir / "code-task-list.md").write_text("- [ ] t1 · task\n", encoding="utf-8")
    worktree = tmp_path / "wt"
    worktree.mkdir()
    write_workspace(
        cycle_dir,
        1,
        "slug-1",
        {"worktree_dir": str(worktree.relative_to(tmp_path)) + "/", "branch": "wt/feat-slug-1"},
        [{"task_id": "t1", "target_repo": "repo-a", "task_worktree": "primary"}],
        tmp_path,
    )
    return cycle_dir, worktree


def _fake_git(monkeypatch, worktree: Path):
    path = str(worktree.resolve())
    real_run = subprocess.run

    def _run(cmd, capture_output=True, text=True, check=False):
        if (
            isinstance(cmd, list)
            and len(cmd) >= 4
            and cmd[0] == "git"
            and cmd[1] == "-C"
            and cmd[3] == "rev-parse"
            and cmd[2].rstrip("/") == path
        ):
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        return real_run(cmd, capture_output=capture_output, text=text, check=check)

    monkeypatch.setattr("git_ops.subprocess.run", _run)


def test_validate_preparing_to_executing(tmp_path: Path, monkeypatch):
    cycle_dir, worktree = _setup_validate_session(tmp_path)
    _fake_git(monkeypatch, worktree)
    payload = validate_preparing_to_executing(cycle_dir)
    assert payload["current_state"] == "Executing"
    assert payload["current_task"] == "t1"
    assert payload["worktree_path"].startswith(str(tmp_path.resolve()))


def test_validate_idempotent_executing(tmp_path: Path, monkeypatch):
    cycle_dir, worktree = _setup_validate_session(tmp_path)
    _fake_git(monkeypatch, worktree)
    validate_preparing_to_executing(cycle_dir)
    payload = validate_preparing_to_executing(cycle_dir)
    assert payload["current_state"] == "Executing"
    assert payload["current_task"] == "t1"


def test_validate_rejects_invalid_state(tmp_path: Path):
    cycle_dir, _ = _setup_validate_session(tmp_path)
    ws_path = cycle_dir / "tech" / "code" / "s1" / "workflow-state.md"
    save_workflow_state(ws_path, {"current_state": "Closing", "current_task": "", "current_phase": ""})
    with pytest.raises(ValueError, match="requires Preparing"):
        validate_preparing_to_executing(cycle_dir)


def test_validate_cli(tmp_path: Path):
    cycle_dir, worktree = _setup_validate_session(tmp_path)
    subprocess.run(["git", "init"], cwd=worktree, capture_output=True, check=True)
    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--cycle-dir",
            str(cycle_dir),
            "--project-root",
            str(tmp_path),
            "--validate",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["current_task"] == "t1"
