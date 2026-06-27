#!/usr/bin/env python3
"""Tests for task_control.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tc_confirm_task_ready import confirm_task_ready  # noqa: E402
from tc_task_control import (  # noqa: E402
    commit_amend_cmd,
    commit_initial_cmd,
    enter_phase_cmd,
    mark_done_cmd,
    resolve_context_cmd,
    run_tests_cmd,
)
from tc_workflow_state_schema import init_preparing, save_workflow_state  # noqa: E402

_SCRIPT = Path(__file__).resolve().parents[1] / "tc_task_control.py"


def _write_wo_session_state(cycle_dir: Path) -> None:
    wo_dir = cycle_dir / "tech" / "work-order"
    wo_dir.mkdir(parents=True, exist_ok=True)
    (wo_dir / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    task_dir = wo_dir / "r1" / "tasks" / "t1"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.md").write_text(
        "---\ntarget_repo: repo-a\nexecution_worktree: feature_worktree\n---\n# First task\n",
        encoding="utf-8",
    )


def _write_workflow_config(project_root: Path) -> None:
    config_dir = project_root / "skill-config" / "lulu-dev-workflow"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "workflow-config.json").write_text(
        json.dumps(
            {
                "tech-code": {
                    "test_command": "echo test-output",
                    "git": {
                        "commit_message_template": "feat({scope}): {task_id} {summary}",
                    },
                }
            }
        ),
        encoding="utf-8",
    )


def _setup_cycle(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    cycle_dir = tmp_path / "cycle"
    project_root = tmp_path / "project"
    project_root.mkdir()
    worktree = tmp_path / "wt"
    worktree.mkdir()
    _write_wo_session_state(cycle_dir)
    _write_workflow_config(project_root)

    session_dir = cycle_dir / "tech" / "code" / "s1"
    session_dir.mkdir(parents=True)
    (cycle_dir / "tech" / "code" / "session-state.md").write_text(
        "---\nversion: 1\nactive_session: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    (session_dir / "code-task-list.md").write_text("- [ ] t1 · First task\n", encoding="utf-8")
    (session_dir / "workspace.json").write_text(
        json.dumps(
            {
                "worktree_path": str(worktree.resolve()).rstrip("/") + "/",
                "project_root": str(project_root.resolve()),
                "branch": "wt/feat-test",
                "created_at": "2024-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    ws_path = session_dir / "workflow-state.md"
    init_preparing(ws_path, mode="work-order", task_list_ref=str(session_dir / "code-task-list.md"))
    save_workflow_state(
        ws_path,
        {"current_state": "Executing", "current_task": "t1", "current_phase": ""},
    )
    return cycle_dir, project_root, worktree, session_dir


class TestResolveContext:
    def test_resolve_context_no_model(self, tmp_path: Path):
        cycle_dir, project_root, _, _ = _setup_cycle(tmp_path)
        result = resolve_context_cmd(cycle_dir, "t1", project_root)
        assert result["task_id"] == "t1"
        assert "model" not in result
        assert result["branch"] == "wt/feat-test"


class TestEnterPhase:
    def test_enter_phase(self, tmp_path: Path):
        cycle_dir, project_root, _, session_dir = _setup_cycle(tmp_path)
        enter_phase_cmd(cycle_dir, "t1", project_root, "WriteTests")
        log = (session_dir / "tasks" / "t1" / "code-log.md").read_text(encoding="utf-8")
        assert "enter · WriteTests" in log


class TestRunTests:
    def test_run_tests_green(self, tmp_path: Path, monkeypatch):
        cycle_dir, project_root, _, session_dir = _setup_cycle(tmp_path)

        def _run(**kwargs):
            return SimpleNamespace(
                exit_code=0,
                command="echo test-output",
                duration_ms=1,
                passed=True,
                output="ok\n",
            )

        monkeypatch.setattr("tc_task_control.execute_test_command", _run)
        result = run_tests_cmd(cycle_dir, "t1", project_root, "green")
        assert result["passed"] is True
        log = (session_dir / "tasks" / "t1" / "code-log.md").read_text(encoding="utf-8")
        assert "test_run · PASS" in log

    def test_run_tests_red_all_pass_fails(self, tmp_path: Path, monkeypatch):
        cycle_dir, project_root, _, _ = _setup_cycle(tmp_path)

        def _run(**kwargs):
            return SimpleNamespace(
                exit_code=0,
                command="echo test-output",
                duration_ms=1,
                passed=True,
                output="ok\n",
            )

        monkeypatch.setattr("tc_task_control.execute_test_command", _run)
        with pytest.raises(ValueError, match="all tests passed unexpectedly"):
            run_tests_cmd(cycle_dir, "t1", project_root, "red")


class TestCommitInitial:
    def test_commit_initial(self, tmp_path: Path, monkeypatch):
        cycle_dir, project_root, worktree, session_dir = _setup_cycle(tmp_path)
        (worktree / "file.txt").write_text("change\n", encoding="utf-8")

        monkeypatch.setattr("tc_task_control.git_add_all", lambda _p: None)
        monkeypatch.setattr("tc_task_control.git_commit", lambda _p, _m: "sha111")
        result = commit_initial_cmd(cycle_dir, "t1", project_root)
        assert result["initial_commit"] == "sha111"
        ref = (session_dir / "tasks" / "t1" / "commit-ref.md").read_text(encoding="utf-8")
        assert "initial_commit: sha111" in ref
        log = (session_dir / "tasks" / "t1" / "code-log.md").read_text(encoding="utf-8")
        assert "git_commit · initial" in log


class TestCommitAmend:
    def test_commit_amend_skipped_when_clean(self, tmp_path: Path, monkeypatch):
        cycle_dir, project_root, _, session_dir = _setup_cycle(tmp_path)
        task_dir = session_dir / "tasks" / "t1"
        task_dir.mkdir(parents=True)
        (task_dir / "commit-ref.md").write_text(
            "task_id: t1\n"
            "branch: wt/feat-test\n"
            "initial_commit: sha111\n"
            "final_commit: sha111\n"
            'commit_message: "feat(code): t1 First task"\n'
            "amended: false\n"
            "recorded_at: 2024-01-01T00:00:00Z\n",
            encoding="utf-8",
        )
        monkeypatch.setattr("tc_task_control.status_clean", lambda _p: True)
        result = commit_amend_cmd(cycle_dir, "t1", project_root)
        assert result["skipped"] is True


class TestMarkDone:
    def test_mark_done(self, tmp_path: Path):
        cycle_dir, project_root, _, session_dir = _setup_cycle(tmp_path)
        mark_done_cmd(cycle_dir, "t1", project_root)
        task_list = (session_dir / "code-task-list.md").read_text(encoding="utf-8")
        assert "- [x] t1" in task_list
        log = (session_dir / "tasks" / "t1" / "code-log.md").read_text(encoding="utf-8")
        assert "enter · Done" in log


class TestIntegrationHappyPath:
    def test_full_mechanical_path_satisfies_confirm_gate(self, tmp_path: Path, monkeypatch):
        cycle_dir, project_root, _, session_dir = _setup_cycle(tmp_path)

        monkeypatch.setattr(
            "tc_task_control.execute_test_command",
            lambda **kwargs: SimpleNamespace(
                exit_code=0,
                command="echo test-output",
                duration_ms=1,
                passed=True,
                output="ok\n",
            ),
        )
        monkeypatch.setattr("tc_task_control.git_add_all", lambda _p: None)
        monkeypatch.setattr("tc_task_control.git_commit", lambda _p, _m: "sha111")
        monkeypatch.setattr("tc_task_control.status_clean", lambda _p: True)

        enter_phase_cmd(cycle_dir, "t1", project_root, "WriteTests")
        run_tests_cmd(cycle_dir, "t1", project_root, "green")
        commit_initial_cmd(cycle_dir, "t1", project_root)
        mark_done_cmd(cycle_dir, "t1", project_root)

        from tc_workflow_state_schema import load_workflow_state  # noqa: E402

        state = load_workflow_state(session_dir / "workflow-state.md")
        result = confirm_task_ready(session_dir, "t1", workflow_state=state)
        assert result["initial_commit"] == "sha111"
        assert result["next_task_id"] is None


class TestCLI:
    def test_resolve_context_cli(self, tmp_path: Path):
        cycle_dir, project_root, _, _ = _setup_cycle(tmp_path)
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-dir",
                str(cycle_dir),
                "--project-root",
                str(project_root),
                "resolve-context",
                "--task-id",
                "t1",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["task_id"] == "t1"
        assert "model" not in payload
