#!/usr/bin/env python3
"""Exit-contract validation after task-runner dispatch (library module).

Imported by session_control.py confirm-task-ready subcommand only.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tc_code_task_list import assert_task_done, next_pending_after, parse_tasks
from tc_commit_ref_schema import load_commit_ref, validate_commit_ref
from tc_session_state_schema import load_work_order_round
from tc_action_receipt_schema import load_receipt, receipt_path
from tc_task_frontmatter import (
    parse_acceptance_criteria,
    parse_kind_from_frontmatter,
    read_task_frontmatter,
)

_CODE_LOG_DONE_RE = re.compile(r"^### .+ · enter · Done\b", re.MULTILINE)


class ExitContractError(Exception):
    """Raised when one or more exit-contract checks fail."""

    def __init__(self, failures: list[tuple[str, str]]) -> None:
        self.failures = failures
        super().__init__(self._format_message())

    @staticmethod
    def _format_message() -> str:
        return "exit contract validation failed"


def _code_log_has_done(path: Path) -> bool:
    if not path.exists():
        return False
    return bool(_CODE_LOG_DONE_RE.search(path.read_text(encoding="utf-8")))


def _task_list_path(session_dir: Path) -> Path:
    return session_dir / "code-task-list.md"


def _work_order_task_path(session_dir: Path, task_id: str) -> Path | None:
    cycle_dir = session_dir.parent.parent
    wo_ss = cycle_dir / "lulu-tasks" / "session-state.md"
    if not wo_ss.exists():
        return None
    try:
        wo_index = f"r{load_work_order_round(wo_ss)}"
    except (ValueError, OSError):
        return None
    return cycle_dir / "lulu-tasks" / wo_index / "tasks" / task_id / "task.md"


def task_kind(session_dir: Path, task_id: str) -> str:
    """Read kind from the work-order task. Default coding when the file is absent."""
    path = _work_order_task_path(session_dir, task_id)
    if path is None:
        return "coding"
    try:
        fm = read_task_frontmatter(path)
    except (ValueError, FileNotFoundError, OSError):
        return "coding"
    return parse_kind_from_frontmatter(fm)


def _acceptance_criteria(session_dir: Path, task_id: str) -> list[str]:
    path = _work_order_task_path(session_dir, task_id)
    if path is None or not path.exists():
        return []
    return parse_acceptance_criteria(path.read_text(encoding="utf-8"))


def confirm_task_ready(
    session_dir: Path, task_id: str, *, workflow_state: dict[str, Any]
) -> dict[str, Any]:
    """Validate exit contract; return checkpoint fields or raise ExitContractError."""
    failures: list[tuple[str, str]] = []

    current_state = workflow_state.get("current_state", "")
    current_task = workflow_state.get("current_task", "")
    if current_state != "Executing":
        failures.append(
            (
                "workflow_pointer",
                f"current_state must be Executing, got {current_state!r}",
            )
        )
    elif current_task != task_id:
        failures.append(
            (
                "workflow_pointer",
                f"current_task must be {task_id!r}, got {current_task!r}",
            )
        )

    kind = task_kind(session_dir, task_id)
    initial_commit: str | None = None
    if kind == "action":
        try:
            load_receipt(
                receipt_path(session_dir, task_id),
                task_id,
                _acceptance_criteria(session_dir, task_id),
            )
        except ValueError as exc:
            failures.append(("receipt", str(exc)))
    else:
        commit_ref_path = session_dir / "tasks" / task_id / "commit-ref.md"
        try:
            data = load_commit_ref(commit_ref_path)
            validate_commit_ref(data, task_id)
            initial_commit = data["initial_commit"]
        except ValueError as exc:
            failures.append(("commit_ref", str(exc)))

        code_log_path = session_dir / "tasks" / task_id / "code-log.md"
        if not _code_log_has_done(code_log_path):
            if not code_log_path.exists():
                failures.append(
                    ("code_log_done", f"code-log.md not found: {code_log_path}")
                )
            else:
                failures.append(
                    (
                        "code_log_done",
                        f"code-log.md missing 'enter · Done' header: {code_log_path}",
                    )
                )

    task_list_path = _task_list_path(session_dir)
    try:
        assert_task_done(task_list_path, task_id)
    except ValueError as exc:
        failures.append(("task_list_done", str(exc)))

    if failures:
        raise ExitContractError(failures)

    tasks = parse_tasks(task_list_path.read_text(encoding="utf-8"))
    next_task_id = next_pending_after(tasks, task_id)

    return {
        "task_id": task_id,
        "kind": kind,
        "initial_commit": initial_commit,
        "next_task_id": next_task_id,
    }
