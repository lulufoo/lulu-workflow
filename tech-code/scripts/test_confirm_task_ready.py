#!/usr/bin/env python3
"""Tests for confirm_task_ready.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from confirm_task_ready import ExitContractError, confirm_task_ready  # noqa: E402


def _session_dir(tmp_path: Path) -> Path:
    session_dir = tmp_path / "s1"
    session_dir.mkdir()
    return session_dir


def _write_task_list(session_dir: Path, lines: list[tuple[str, str]]) -> None:
    body = "\n".join(f"- [{mark}] {task_id} · task" for task_id, mark in lines)
    (session_dir / "code-task-list.md").write_text(body + "\n", encoding="utf-8")


def _write_commit_ref(session_dir: Path, task_id: str, *, initial_commit: str = "abc123") -> None:
    task_dir = session_dir / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "commit-ref.md").write_text(
        f"task_id: {task_id}\n"
        "branch: wt/feat-test\n"
        f"initial_commit: {initial_commit}\n"
        "final_commit: def456\n"
        'commit_message: "feat: test"\n'
        "amended: false\n"
        "recorded_at: 2024-01-01T00:00:00Z\n",
        encoding="utf-8",
    )


def _write_code_log_done(session_dir: Path, task_id: str) -> None:
    task_dir = session_dir / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "code-log.md").write_text(
        "### 2024-01-01T00:00:00Z · enter · Done\n",
        encoding="utf-8",
    )


def _executing_state(*, current_task: str = "t1") -> dict:
    return {
        "current_state": "Executing",
        "current_task": current_task,
        "current_phase": "",
    }


def _setup_complete(session_dir: Path, task_id: str = "t1") -> None:
    _write_task_list(session_dir, [("t1", "x"), ("t2", " ")])
    _write_commit_ref(session_dir, task_id)
    _write_code_log_done(session_dir, task_id)


class TestConfirmTaskReady:
    def test_happy_path_with_next_task(self, tmp_path: Path):
        session_dir = _session_dir(tmp_path)
        _setup_complete(session_dir, "t1")
        result = confirm_task_ready(session_dir, "t1", workflow_state=_executing_state())
        assert result == {
            "task_id": "t1",
            "initial_commit": "abc123",
            "next_task_id": "t2",
        }

    def test_last_task_next_task_id_null(self, tmp_path: Path):
        session_dir = _session_dir(tmp_path)
        _write_task_list(session_dir, [("t1", "x"), ("t2", "x")])
        _write_commit_ref(session_dir, "t2")
        _write_code_log_done(session_dir, "t2")
        result = confirm_task_ready(
            session_dir, "t2", workflow_state=_executing_state(current_task="t2")
        )
        assert result["next_task_id"] is None

    def test_workflow_pointer_wrong_state(self, tmp_path: Path):
        session_dir = _session_dir(tmp_path)
        _setup_complete(session_dir)
        with pytest.raises(ExitContractError) as exc_info:
            confirm_task_ready(
                session_dir,
                "t1",
                workflow_state={"current_state": "Closing", "current_task": "t1"},
            )
        keys = [key for key, _ in exc_info.value.failures]
        assert "workflow_pointer" in keys

    def test_workflow_pointer_wrong_task(self, tmp_path: Path):
        session_dir = _session_dir(tmp_path)
        _setup_complete(session_dir)
        with pytest.raises(ExitContractError) as exc_info:
            confirm_task_ready(session_dir, "t1", workflow_state=_executing_state(current_task="t2"))
        assert exc_info.value.failures == [
            ("workflow_pointer", "current_task must be 't1', got 't2'")
        ]

    def test_missing_commit_ref(self, tmp_path: Path):
        session_dir = _session_dir(tmp_path)
        _write_task_list(session_dir, [("t1", "x")])
        _write_code_log_done(session_dir, "t1")
        with pytest.raises(ExitContractError) as exc_info:
            confirm_task_ready(session_dir, "t1", workflow_state=_executing_state())
        keys = [key for key, _ in exc_info.value.failures]
        assert "commit_ref" in keys

    def test_missing_code_log(self, tmp_path: Path):
        session_dir = _session_dir(tmp_path)
        _write_task_list(session_dir, [("t1", "x")])
        _write_commit_ref(session_dir, "t1")
        with pytest.raises(ExitContractError) as exc_info:
            confirm_task_ready(session_dir, "t1", workflow_state=_executing_state())
        keys = [key for key, _ in exc_info.value.failures]
        assert "code_log_done" in keys

    def test_code_log_missing_done_header(self, tmp_path: Path):
        session_dir = _session_dir(tmp_path)
        _write_task_list(session_dir, [("t1", "x")])
        _write_commit_ref(session_dir, "t1")
        task_dir = session_dir / "tasks" / "t1"
        (task_dir / "code-log.md").write_text(
            "### 2024-01-01T00:00:00Z · enter · VerifyGreen\n",
            encoding="utf-8",
        )
        with pytest.raises(ExitContractError) as exc_info:
            confirm_task_ready(session_dir, "t1", workflow_state=_executing_state())
        keys = [key for key, _ in exc_info.value.failures]
        assert "code_log_done" in keys

    def test_task_not_done(self, tmp_path: Path):
        session_dir = _session_dir(tmp_path)
        _write_task_list(session_dir, [("t1", " "), ("t2", " ")])
        _write_commit_ref(session_dir, "t1")
        _write_code_log_done(session_dir, "t1")
        with pytest.raises(ExitContractError) as exc_info:
            confirm_task_ready(session_dir, "t1", workflow_state=_executing_state())
        keys = [key for key, _ in exc_info.value.failures]
        assert "task_list_done" in keys

    def test_multiple_failures(self, tmp_path: Path):
        session_dir = _session_dir(tmp_path)
        _write_task_list(session_dir, [("t1", " ")])
        with pytest.raises(ExitContractError) as exc_info:
            confirm_task_ready(
                session_dir,
                "t1",
                workflow_state={"current_state": "Preparing", "current_task": ""},
            )
        keys = {key for key, _ in exc_info.value.failures}
        assert keys == {"workflow_pointer", "commit_ref", "code_log_done", "task_list_done"}
