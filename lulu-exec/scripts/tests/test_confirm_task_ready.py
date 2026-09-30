#!/usr/bin/env python3
"""Tests for confirm_task_ready.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tc_action_receipt_schema import receipt_path, save_receipt  # noqa: E402
from tc_confirm_task_ready import ExitContractError, confirm_task_ready  # noqa: E402

_CRITERIA = ["Every todo has a Linear issue", "Missing todos were migrated once"]

_ACTION_TASK = """---
kind: action
title: Todos are migrated to Linear
effects: mutates
mutates: [linear]
exit_contract:
  receipt: required
---
# t1

## Section 1: Acceptance Criteria

- [ ] Every todo has a Linear issue
- [ ] Missing todos were migrated once

## Section 3: Constraints
"""


def _setup_action_task(tmp_path: Path) -> Path:
    cycle_dir = tmp_path / "cycle"
    session_dir = cycle_dir / "lulu-exec" / "s1"
    session_dir.mkdir(parents=True)
    wo = cycle_dir / "lulu-tasks"
    (wo / "r1" / "tasks" / "t1").mkdir(parents=True)
    (wo / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    (wo / "r1" / "tasks" / "t1" / "task.md").write_text(_ACTION_TASK, encoding="utf-8")
    (session_dir / "code-task-list.md").write_text("- [x] t1 · task\n", encoding="utf-8")
    return session_dir


def _full_results() -> list[dict]:
    return [
        {"criterion": criterion, "evidence": f"LIN-1 covers: {criterion}", "met": True}
        for criterion in _CRITERIA
    ]


def _save_action_receipt(session_dir: Path, results: list[dict]) -> None:
    save_receipt(
        receipt_path(session_dir, "t1"),
        {
            "version": 2,
            "task_id": "t1",
            "goal": "Todos are migrated to Linear",
            "effects": "mutates: linear",
            "results": results,
        },
        _CRITERIA,
    )


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
            "kind": "coding",
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

    def test_action_accepts_receipt_without_commit_or_worktree(self, tmp_path: Path):
        session_dir = _setup_action_task(tmp_path)
        _save_action_receipt(session_dir, _full_results())
        result = confirm_task_ready(session_dir, "t1", workflow_state=_executing_state())
        assert result["kind"] == "action"
        assert result["initial_commit"] is None
        assert result["next_task_id"] is None

    def test_action_rejects_receipt_missing_a_criterion(self, tmp_path: Path):
        session_dir = _setup_action_task(tmp_path)
        _save_action_receipt(session_dir, _full_results())
        receipt = receipt_path(session_dir, "t1")
        data = json.loads(receipt.read_text(encoding="utf-8"))
        data["results"] = data["results"][:1]
        receipt.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ExitContractError) as exc_info:
            confirm_task_ready(session_dir, "t1", workflow_state=_executing_state())
        assert [key for key, _ in exc_info.value.failures] == ["receipt"]
        message = exc_info.value.failures[0][1]
        assert "no result for acceptance criterion" in message
        assert "Missing todos were migrated once" in message

    def test_action_requires_receipt_file(self, tmp_path: Path):
        session_dir = _setup_action_task(tmp_path)
        with pytest.raises(ExitContractError) as exc_info:
            confirm_task_ready(session_dir, "t1", workflow_state=_executing_state())
        assert [key for key, _ in exc_info.value.failures] == ["receipt"]
