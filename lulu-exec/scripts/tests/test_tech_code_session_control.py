#!/usr/bin/env python3
"""Tests for session_control.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from types import SimpleNamespace

from tc_confirm_task_ready import ExitContractError  # noqa: E402
from tc_session_control import (  # noqa: E402
    advance_pointer,
    check_recovery,
    confirm_task_ready_cmd,
    deliver,
    get_pointer,
)
from tc_workflow_state_schema import (  # noqa: E402
    init_preparing,
    init_starting,
    mark_historical,
    save_workflow_state,
)

_SCRIPT = Path(__file__).resolve().parents[1] / "tc_session_control.py"


def _setup_session(tmp_path: Path, *, state: str = "Preparing", current_task: str = "") -> Path:
    cycle_dir = tmp_path / "cycle-id"
    session_dir = cycle_dir / "lulu-exec" / "s1"
    session_dir.mkdir(parents=True)
    (cycle_dir / "lulu-exec" / "session-state.md").write_text(
        "---\nversion: 1\nactive_session: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    ws_path = session_dir / "workflow-state.md"
    init_preparing(ws_path, mode="work-order", task_list_ref=str(session_dir / "code-task-list.md"))
    if state != "Preparing":
        save_workflow_state(
            ws_path,
            {
                "current_state": state,
                "current_task": current_task,
                "current_phase": "",
            },
        )
    return cycle_dir


def _write_task_list(session_dir: Path, lines: list[str]) -> None:
    body = "\n".join(f"- [{mark}] {task_id} · task" for task_id, mark in lines)
    (session_dir / "code-task-list.md").write_text(body + "\n", encoding="utf-8")


def _write_workspace(
    session_dir: Path,
    worktree_path: Path,
    extra: dict | None = None,
    project_root: Path | None = None,
) -> None:
    payload = {
        "worktree_path": str(worktree_path.resolve()).rstrip("/") + "/",
        "project_root": str((project_root or session_dir).resolve()),
        "branch": "wt/feat-test",
        "created_at": "2024-01-01T00:00:00+00:00",
    }
    if extra:
        payload["extra_worktrees"] = extra
    (session_dir / "workspace.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_code_log_done(session_dir: Path, task_id: str) -> None:
    task_dir = session_dir / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "code-log.md").write_text(
        "### 2024-01-01T00:00:00Z · enter · Done\n",
        encoding="utf-8",
    )


def _write_commit_ref(session_dir: Path, task_id: str) -> None:
    task_dir = session_dir / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "commit-ref.md").write_text(
        f"task_id: {task_id}\n"
        "branch: wt/feat-test\n"
        "initial_commit: abc123\n"
        "final_commit: def456\n"
        "commit_message: \"feat: test\"\n"
        "amended: false\n"
        "recorded_at: 2024-01-01T00:00:00Z\n",
        encoding="utf-8",
    )


def _fake_git(monkeypatch, *, worktrees: set[str], clean: set[str]):
    def _run(cmd, capture_output=True, text=True, check=False):
        if cmd[:4] == ["git", "-C", cmd[2], "rev-parse"]:
            path = cmd[2].rstrip("/")
            stdout = "true\n" if path in worktrees else "false\n"
            return subprocess.CompletedProcess(cmd, 0 if path in worktrees else 1, stdout, "")
        if cmd[:4] == ["git", "-C", cmd[2], "status"]:
            path = cmd[2].rstrip("/")
            stdout = "" if path in clean else " M dirty\n"
            return subprocess.CompletedProcess(cmd, 0, stdout, "")
        raise AssertionError(f"unexpected git command: {cmd}")

    monkeypatch.setattr("tc_git_ops.subprocess.run", _run)


class TestGetPointer:
    def test_starting(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path)
        ws_path = cycle_dir / "lulu-exec" / "s1" / "workflow-state.md"
        init_starting(ws_path, mode="work-order", task_list_ref=str(ws_path.parent / "code-task-list.md"))
        ptr = get_pointer(cycle_dir)
        assert ptr["next_action"] == "starting"
        assert ptr["current_state"] == "Starting"

    def test_preparing(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path)
        ptr = get_pointer(cycle_dir)
        assert ptr["next_action"] == "prepare"
        assert ptr["current_state"] == "Preparing"

    def test_executing_dispatch(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", " "), ("t2", " ")])
        ptr = get_pointer(cycle_dir)
        assert ptr["next_action"] == "dispatch"
        assert ptr["current_task"] == "t1"

    def test_executing_pointer_drift(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x"), ("t2", " ")])
        with pytest.raises(ValueError, match="pointer drift"):
            get_pointer(cycle_dir)

    def test_closing(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Closing")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x")])
        _write_commit_ref(session_dir, "t1")
        ptr = get_pointer(cycle_dir)
        assert ptr["next_action"] == "closing"

    def test_closing_malformed_commit_ref(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Closing")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x")])
        task_dir = session_dir / "tasks" / "t1"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "commit-ref.md").write_text("---\ninitial_commit: bad\n---\n", encoding="utf-8")
        with pytest.raises(ValueError, match="missing required fields"):
            get_pointer(cycle_dir)

    def test_delivered_done(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Delivered")
        ptr = get_pointer(cycle_dir)
        assert ptr["next_action"] == "done"

    def test_subagent_empty_without_workspace(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", " "), ("t2", " ")])
        ptr = get_pointer(cycle_dir)
        assert ptr["subagent"] == ""

    def test_subagent_uses_project_config(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", " "), ("t2", " ")])
        project_root = tmp_path / "project"
        stage_path = project_root / ".cursor" / "lulu-workflow" / "stages" / "lulu-exec.json"
        stage_path.parent.mkdir(parents=True)
        stage_path.write_text(
            json.dumps({"test_commands": {}, "subagent": "composer-2.5-fast"}),
            encoding="utf-8",
        )
        worktree = tmp_path / "wt"
        worktree.mkdir()
        _write_workspace(session_dir, worktree, project_root=project_root)
        ptr = get_pointer(cycle_dir)
        assert ptr["subagent"] == "composer-2.5-fast"

    def test_subagent_ignores_legacy_object(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", " "), ("t2", " ")])
        project_root = tmp_path / "project"
        stage_path = project_root / ".cursor" / "lulu-workflow" / "stages" / "lulu-exec.json"
        stage_path.parent.mkdir(parents=True)
        stage_path.write_text(
            json.dumps({"subagent": {"cursor": "composer-2.5-fast"}}),
            encoding="utf-8",
        )
        worktree = tmp_path / "wt"
        worktree.mkdir()
        _write_workspace(session_dir, worktree, project_root=project_root)
        ptr = get_pointer(cycle_dir)
        assert ptr["subagent"] == ""


class TestAdvancePointer:
    def test_middle_task(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x"), ("t2", " "), ("t3", " ")])
        ptr = advance_pointer(cycle_dir, "t1")
        assert ptr["next_action"] == "dispatch"
        assert ptr["current_task"] == "t2"
        assert ptr["previous_task"] == "t1"

    def test_last_task_to_closing_malformed_commit_ref(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t2")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x"), ("t2", "x")])
        _write_commit_ref(session_dir, "t1")
        task_dir = session_dir / "tasks" / "t2"
        task_dir.mkdir(parents=True, exist_ok=True)
        (task_dir / "commit-ref.md").write_text("---\ninitial_commit: bad\n---\n", encoding="utf-8")
        with pytest.raises(ValueError, match="missing required fields"):
            advance_pointer(cycle_dir, "t2")

    def test_last_task_to_closing(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t2")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x"), ("t2", "x")])
        _write_commit_ref(session_dir, "t1")
        _write_commit_ref(session_dir, "t2")
        ptr = advance_pointer(cycle_dir, "t2")
        assert ptr["next_action"] == "closing"
        assert ptr["current_state"] == "Closing"

    def test_mismatch_completed_task(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x"), ("t2", " ")])
        with pytest.raises(ValueError, match="does not match current_task"):
            advance_pointer(cycle_dir, "t2")

    def test_task_not_done(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", " "), ("t2", " ")])
        with pytest.raises(ValueError, match="not marked done"):
            advance_pointer(cycle_dir, "t1")


class TestDeliver:
    def test_deliver_success(self, tmp_path: Path, monkeypatch):
        cycle_dir = _setup_session(tmp_path, state="Closing")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        worktree = tmp_path / "wt"
        worktree.mkdir()
        _write_task_list(session_dir, [("t1", "x")])
        _write_commit_ref(session_dir, "t1")
        _write_workspace(session_dir, worktree)
        _fake_git(monkeypatch, worktrees={str(worktree.resolve())}, clean={str(worktree.resolve())})

        def _mock_run_test_suite(**kwargs):
            return SimpleNamespace(exit_code=0, command="npm test", duration_ms=1, passed=True)

        monkeypatch.setattr("tc_session_control.run_test_suite", _mock_run_test_suite)
        ptr = deliver(cycle_dir, tmp_path)
        assert ptr["next_action"] == "done"
        assert ptr["current_state"] == "Delivered"
        checklist = (session_dir / "closing-checklist.md").read_text(encoding="utf-8")
        assert "- [x] Full test suite re-run (PASS)" in checklist

    def test_deliver_requires_closing(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        with pytest.raises(ValueError, match="requires Closing"):
            deliver(cycle_dir, tmp_path)

    def test_deliver_test_failure_state_stays_closing(self, tmp_path: Path, monkeypatch):
        cycle_dir = _setup_session(tmp_path, state="Closing")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        ws_path = session_dir / "workflow-state.md"
        worktree = tmp_path / "wt"
        worktree.mkdir()
        _write_task_list(session_dir, [("t1", "x")])
        _write_commit_ref(session_dir, "t1")
        _write_workspace(session_dir, worktree)
        _fake_git(monkeypatch, worktrees={str(worktree.resolve())}, clean={str(worktree.resolve())})

        def _mock_run_test_suite(**kwargs):
            return SimpleNamespace(exit_code=1, command="npm test", duration_ms=1, passed=False)

        monkeypatch.setattr("tc_session_control.run_test_suite", _mock_run_test_suite)
        with pytest.raises(ValueError, match="test suite failed"):
            deliver(cycle_dir, tmp_path)
        from tc_workflow_state_schema import load_workflow_state  # noqa: E402

        assert load_workflow_state(ws_path)["current_state"] == "Closing"


class TestCheckRecovery:
    def test_no_session_state(self, tmp_path: Path):
        cycle_dir = tmp_path / "cycle-id"
        result = check_recovery(cycle_dir)
        assert result == {
            "recoverable": False,
            "resume_section": "Starting",
            "reason": "no_session",
        }

    @pytest.mark.parametrize("state", ["Starting", "Preparing", "Delivered"])
    def test_terminal_states(self, tmp_path: Path, state: str):
        cycle_dir = _setup_session(tmp_path, state=state)
        result = check_recovery(cycle_dir)
        assert result["recoverable"] is False
        assert result["resume_section"] == "Starting"
        assert result["reason"] == "terminal_state"

    def test_historical(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path)
        ws_path = cycle_dir / "lulu-exec" / "s1" / "workflow-state.md"
        mark_historical(ws_path)
        result = check_recovery(cycle_dir)
        assert result["recoverable"] is False
        assert result["reason"] == "historical"

    def test_missing_workflow_state(self, tmp_path: Path):
        cycle_dir = tmp_path / "cycle-id"
        (cycle_dir / "lulu-exec").mkdir(parents=True)
        (cycle_dir / "lulu-exec" / "session-state.md").write_text(
            "---\nversion: 1\nactive_session: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
            encoding="utf-8",
        )
        result = check_recovery(cycle_dir)
        assert result["recoverable"] is False
        assert result["reason"] == "missing_workflow_state"

    def test_executing_valid_pending_task(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", " "), ("t2", " ")])
        result = check_recovery(cycle_dir)
        assert result["recoverable"] is True
        assert result["resume_section"] == "Executing"
        assert result["current_task"] == "t1"
        assert result["active_session"] == 1

    def test_executing_empty_current_task(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", " ")])
        result = check_recovery(cycle_dir)
        assert result["recoverable"] is False
        assert result["reason"] == "empty_current_task"

    def test_executing_missing_task_list(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        result = check_recovery(cycle_dir)
        assert result["recoverable"] is False
        assert result["reason"] == "missing_task_list"

    def test_executing_unknown_task(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t9")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", " ")])
        result = check_recovery(cycle_dir)
        assert result["recoverable"] is False
        assert result["reason"] == "unknown_current_task"

    def test_executing_pointer_unrecoverable(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x"), ("t2", " ")])
        result = check_recovery(cycle_dir)
        assert result["recoverable"] is False
        assert result["reason"] == "pointer_unrecoverable"

    def test_closing(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Closing")
        result = check_recovery(cycle_dir)
        assert result["recoverable"] is True
        assert result["resume_section"] == "Closing"
        assert result["active_session"] == 1

    def test_drift_matches_get_pointer(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x"), ("t2", " ")])
        assert check_recovery(cycle_dir)["recoverable"] is False
        with pytest.raises(ValueError, match="pointer drift"):
            get_pointer(cycle_dir)


class TestConfirmTaskReady:
    def test_complete_artifacts(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x"), ("t2", " ")])
        _write_commit_ref(session_dir, "t1")
        _write_code_log_done(session_dir, "t1")
        result = confirm_task_ready_cmd(cycle_dir, "t1")
        assert result["task_id"] == "t1"
        assert result["initial_commit"] == "abc123"
        assert result["next_task_id"] == "t2"

    def test_missing_artifact_raises(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x"), ("t2", " ")])
        with pytest.raises(ExitContractError):
            confirm_task_ready_cmd(cycle_dir, "t1")


class TestCLI:
    def test_get_pointer_cli(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path)
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--cycle-dir", str(cycle_dir), "get-pointer"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert json.loads(result.stdout)["next_action"] == "prepare"

    def test_confirm_task_ready_cli_success(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x"), ("t2", " ")])
        _write_commit_ref(session_dir, "t1")
        _write_code_log_done(session_dir, "t1")
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-dir",
                str(cycle_dir),
                "confirm-task-ready",
                "--task-id",
                "t1",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["initial_commit"] == "abc123"
        assert payload["next_task_id"] == "t2"

    def test_confirm_task_ready_cli_missing_artifact(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", "x"), ("t2", " ")])
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT),
                "--cycle-dir",
                str(cycle_dir),
                "confirm-task-ready",
                "--task-id",
                "t1",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "exit contract failed:" in result.stderr

    def test_check_recovery_cli(self, tmp_path: Path):
        cycle_dir = _setup_session(tmp_path, state="Executing", current_task="t1")
        session_dir = cycle_dir / "lulu-exec" / "s1"
        _write_task_list(session_dir, [("t1", " "), ("t2", " ")])
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--cycle-dir", str(cycle_dir), "check-recovery"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["recoverable"] is True
        assert payload["resume_section"] == "Executing"
