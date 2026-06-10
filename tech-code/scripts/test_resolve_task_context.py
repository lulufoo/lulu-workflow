#!/usr/bin/env python3
"""Tests for resolve_task_context.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_task_context import resolve_task_context  # noqa: E402


def _write_wo_session_state(cycle_dir: Path, round_id: str = "1") -> None:
    wo_dir = cycle_dir / "tech" / "work-order"
    wo_dir.mkdir(parents=True, exist_ok=True)
    (wo_dir / "session-state.md").write_text(
        f"---\nversion: 1\nactive_doc: {round_id}\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    round_dir = wo_dir / f"r{round_id}" / "tasks" / "t1"
    round_dir.mkdir(parents=True, exist_ok=True)
    (round_dir / "task.md").write_text("# t1\n", encoding="utf-8")


def _write_code_session_state(cycle_dir: Path, session_id: str = "1") -> Path:
    code_dir = cycle_dir / "tech" / "code"
    code_dir.mkdir(parents=True, exist_ok=True)
    (code_dir / "session-state.md").write_text(
        f"---\nversion: 1\nactive_session: {session_id}\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    session_dir = code_dir / f"s{session_id}"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "code-task-list.md").write_text("- [ ] t1 · task\n", encoding="utf-8")
    return session_dir


def _write_workspace(session_dir: Path, worktree_path: Path) -> None:
    payload = {
        "worktree_path": str(worktree_path.resolve()).rstrip("/") + "/",
        "project_root": str(session_dir.resolve()),
        "primary_repo": "repo-a",
        "branch": "wt/feat-test",
        "created_at": "2024-01-01T00:00:00+00:00",
    }
    (session_dir / "workspace.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_workflow_config(project_root: Path) -> None:
    config_dir = project_root / "skill-config" / "lulu-dev-workflow"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "workflow-config.json").write_text(
        json.dumps(
            {
                "tech-code": {
                    "test_command": "npm test",
                    "git": {
                        "worktree_base": ".cache/worktrees",
                        "branch_pattern": "wt/{type}-{slug}",
                        "default_type": "feat",
                        "commit_message_template": "feat({scope}): {subject}",
                    },
                }
            }
        ),
        encoding="utf-8",
    )


def _setup_happy_path(tmp_path: Path) -> tuple[Path, Path, Path]:
    cycle_dir = tmp_path / "cycle"
    project_root = tmp_path / "project"
    worktree = tmp_path / "wt"
    worktree.mkdir()
    _write_wo_session_state(cycle_dir)
    session_dir = _write_code_session_state(cycle_dir)
    _write_workspace(session_dir, worktree)
    _write_workflow_config(project_root)
    return cycle_dir, project_root, worktree


class TestResolveTaskContext:
    def test_happy_path(self, tmp_path: Path):
        cycle_dir, project_root, worktree = _setup_happy_path(tmp_path)
        result = resolve_task_context(cycle_dir, "t1", project_root)

        assert set(result) == {
            "task_id",
            "work_order_task_path",
            "task_output_dir",
            "code_task_list_path",
            "worktree_abs_path",
            "commit_message_template",
            "test_command",
        }
        assert result["task_id"] == "t1"
        assert "/work-order/r1/tasks/t1/task.md" in result["work_order_task_path"]
        assert "/code/s1/tasks/t1" in result["task_output_dir"]
        assert "/code/s1/code-task-list.md" in result["code_task_list_path"]
        assert result["worktree_abs_path"] == str(worktree.resolve())
        assert result["test_command"] == "npm test"
        assert result["commit_message_template"] == "feat({scope}): {subject}"

    def test_missing_work_order_session_state(self, tmp_path: Path):
        cycle_dir = tmp_path / "cycle"
        project_root = tmp_path / "project"
        _write_code_session_state(cycle_dir)
        _write_workflow_config(project_root)
        with pytest.raises(ValueError, match="session-state.md not found"):
            resolve_task_context(cycle_dir, "t1", project_root)

    def test_missing_code_session_state(self, tmp_path: Path):
        cycle_dir = tmp_path / "cycle"
        project_root = tmp_path / "project"
        _write_wo_session_state(cycle_dir)
        _write_workflow_config(project_root)
        with pytest.raises(ValueError, match="session-state.md not found"):
            resolve_task_context(cycle_dir, "t1", project_root)

    def test_missing_workspace_json(self, tmp_path: Path):
        cycle_dir = tmp_path / "cycle"
        project_root = tmp_path / "project"
        _write_wo_session_state(cycle_dir)
        _write_code_session_state(cycle_dir)
        _write_workflow_config(project_root)
        with pytest.raises(ValueError, match="workspace.json not found"):
            resolve_task_context(cycle_dir, "t1", project_root)

    def test_missing_workflow_config(self, tmp_path: Path):
        cycle_dir, project_root, _ = _setup_happy_path(tmp_path)
        config_path = project_root / "skill-config" / "lulu-dev-workflow" / "workflow-config.json"
        config_path.unlink()
        with pytest.raises(ValueError, match="workflow-config.json not found"):
            resolve_task_context(cycle_dir, "t1", project_root)
