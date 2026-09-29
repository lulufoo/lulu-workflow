#!/usr/bin/env python3
"""Session pointer control for lulu-code orchestrator.

Subcommands:
    check-recovery       Read-only entry probe for Executing/Closing recovery
    get-pointer          Read workflow-state and return PointerResponse JSON
    confirm-task-ready   Validate task-runner exit contract after dispatch
    advance-pointer      Advance after a completed task
    deliver              Transition Closing -> Delivered
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tc_closing_checklist_schema import write_passed  # noqa: E402
from tc_confirm_task_ready import ExitContractError, confirm_task_ready, task_kind  # noqa: E402
from tc_commit_ref_schema import validate_session_commit_refs  # noqa: E402
from tc_code_task_list import (  # noqa: E402
    all_done,
    assert_task_done,
    first_pending,
    next_pending_after,
    parse_tasks,
)
from tc_git_ops import validate_session_worktrees_clean  # noqa: E402
from tc_run_test_suite import run_test_suite  # noqa: E402
from tc_session_state_schema import load_session_state  # noqa: E402
from tc_workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path,
    save_workflow_state,
)
from tc_workspace_schema import load_workspace  # noqa: E402
from tc_workflow_common import exec_stage_dir  # noqa: E402


def _session_dir(cycle_dir: Path) -> Path:
    stage_dir = exec_stage_dir(cycle_dir)
    active = load_session_state(stage_dir / "session-state.md")
    return stage_dir / f"s{active}"


def _task_list_path(session_dir: Path) -> Path:
    return session_dir / "code-task-list.md"


def _workspace_path(session_dir: Path) -> Path:
    return session_dir / "workspace.json"


def _validate_closing_ready(session_dir: Path) -> list[dict]:
    """Lightweight Closing readiness: all tasks done + commit-ref schema validation."""
    task_list_path = _task_list_path(session_dir)
    if not task_list_path.exists():
        raise ValueError(f"code-task-list.md not found: {task_list_path}")

    tasks = parse_tasks(task_list_path.read_text(encoding="utf-8"))
    if not tasks:
        raise ValueError("code-task-list.md has no tasks")
    if not all_done(tasks):
        raise ValueError("not all tasks are marked done in code-task-list.md")

    coding_tasks = [task for task in tasks if task_kind(session_dir, task["id"]) == "coding"]
    validate_session_commit_refs(session_dir, coding_tasks)
    return tasks


def _task_is_done(task_list_path: Path, task_id: str) -> bool:
    for task in parse_tasks(task_list_path.read_text(encoding="utf-8")):
        if task["id"] == task_id:
            return task["done"]
    return False


def _executing_recoverable(session_dir: Path, current_task: str) -> tuple[bool, str | None]:
    """Return whether an Executing session can resume dispatch without pointer drift."""
    if not current_task:
        return False, "empty_current_task"
    task_list_path = _task_list_path(session_dir)
    if not task_list_path.exists():
        return False, "missing_task_list"
    tasks = parse_tasks(task_list_path.read_text(encoding="utf-8"))
    if not any(task["id"] == current_task for task in tasks):
        return False, "unknown_current_task"
    if _task_is_done(task_list_path, current_task):
        return False, "pointer_unrecoverable"
    return True, None


def _executing_unrecoverable_error(
    session_dir: Path, current_task: str, reason: str
) -> ValueError:
    if reason == "empty_current_task":
        return ValueError("Executing state requires current_task")
    if reason == "missing_task_list":
        return ValueError(f"code-task-list.md not found: {_task_list_path(session_dir)}")
    if reason == "unknown_current_task":
        return ValueError(f"unknown current_task {current_task!r} in code-task-list.md")
    if reason == "pointer_unrecoverable":
        return ValueError(
            f"pointer drift: current_task {current_task} is already done in code-task-list.md"
        )
    return ValueError(f"Executing session not recoverable: {reason}")


def _build_pointer(
    *,
    current_state: str,
    current_task: str,
    next_action: str,
    previous_task: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "current_state": current_state,
        "current_task": current_task,
        "next_action": next_action,
    }
    if previous_task is not None:
        payload["previous_task"] = previous_task
    return payload


def get_pointer(cycle_dir: Path) -> dict[str, Any]:
    ws_path = resolve_workflow_state_path(cycle_dir)
    state = load_workflow_state(ws_path)
    session_dir = ws_path.parent
    current_state = state["current_state"]

    if current_state == "Starting":
        return _build_pointer(
            current_state=current_state,
            current_task="",
            next_action="starting",
        )

    if current_state == "Preparing":
        return _build_pointer(
            current_state=current_state,
            current_task=state.get("current_task", ""),
            next_action="prepare",
        )

    if current_state == "Executing":
        current_task = state.get("current_task", "")
        recoverable, reason = _executing_recoverable(session_dir, current_task)
        if not recoverable:
            raise _executing_unrecoverable_error(session_dir, current_task, reason or "")
        pointer = _build_pointer(
            current_state=current_state,
            current_task=current_task,
            next_action="dispatch",
        )
        pointer["kind"] = task_kind(session_dir, current_task)
        return pointer

    if current_state == "Closing":
        _validate_closing_ready(session_dir)
        return _build_pointer(
            current_state=current_state,
            current_task="",
            next_action="closing",
        )

    if current_state == "Delivered":
        return _build_pointer(
            current_state=current_state,
            current_task="",
            next_action="done",
        )

    raise ValueError(f"unsupported current_state: {current_state}")


def check_recovery(cycle_dir: Path) -> dict[str, Any]:
    """Read-only entry probe; does not run get-pointer validations."""
    ss_path = exec_stage_dir(cycle_dir) / "session-state.md"
    if not ss_path.exists():
        return {
            "recoverable": False,
            "resume_section": "Starting",
            "reason": "no_session",
        }

    active_session = load_session_state(ss_path)
    ws_path = exec_stage_dir(cycle_dir) / f"s{active_session}" / "workflow-state.md"
    if not ws_path.exists():
        return {
            "recoverable": False,
            "resume_section": "Starting",
            "reason": "missing_workflow_state",
        }

    state = load_workflow_state(ws_path)
    if state.get("historical") == "true":
        return {
            "recoverable": False,
            "resume_section": "Starting",
            "reason": "historical",
        }

    current_state = state["current_state"]
    if current_state in ("Starting", "Preparing", "Delivered"):
        return {
            "recoverable": False,
            "resume_section": "Starting",
            "reason": "terminal_state",
        }

    if current_state == "Executing":
        session_dir = ws_path.parent
        current_task = state.get("current_task", "")
        recoverable, reason = _executing_recoverable(session_dir, current_task)
        if not recoverable:
            return {
                "recoverable": False,
                "resume_section": "Starting",
                "reason": reason,
            }
        return {
            "recoverable": True,
            "resume_section": "Executing",
            "current_state": current_state,
            "current_task": current_task,
            "active_session": active_session,
        }

    if current_state == "Closing":
        return {
            "recoverable": True,
            "resume_section": "Closing",
            "current_state": current_state,
            "active_session": active_session,
        }

    return {
        "recoverable": False,
        "resume_section": "Starting",
        "reason": "terminal_state",
    }


def confirm_task_ready_cmd(cycle_dir: Path, task_id: str) -> dict[str, Any]:
    session_dir = _session_dir(cycle_dir)
    ws_path = session_dir / "workflow-state.md"
    state = load_workflow_state(ws_path)
    return confirm_task_ready(session_dir, task_id, workflow_state=state)


def advance_pointer(cycle_dir: Path, completed_task: str) -> dict[str, Any]:
    ws_path = resolve_workflow_state_path(cycle_dir)
    state = load_workflow_state(ws_path)
    session_dir = ws_path.parent

    if state["current_state"] != "Executing":
        raise ValueError(
            f"advance-pointer requires Executing, got {state['current_state']!r}"
        )

    current_task = state.get("current_task", "")
    if completed_task != current_task:
        raise ValueError(
            f"completed task {completed_task!r} does not match current_task {current_task!r}"
        )

    task_list_path = _task_list_path(session_dir)
    assert_task_done(task_list_path, completed_task)

    tasks = parse_tasks(task_list_path.read_text(encoding="utf-8"))
    next_task = next_pending_after(tasks, completed_task)
    if next_task:
        save_workflow_state(
            ws_path,
            {
                "current_state": "Executing",
                "current_task": next_task,
                "current_phase": "",
            },
        )
        pointer = _build_pointer(
            current_state="Executing",
            current_task=next_task,
            next_action="dispatch",
            previous_task=completed_task,
        )
        pointer["kind"] = task_kind(session_dir, next_task)
        return pointer

    _validate_closing_ready(session_dir)
    save_workflow_state(
        ws_path,
        {
            "current_state": "Closing",
            "current_task": "",
            "current_phase": "",
        },
    )
    return _build_pointer(
        current_state="Closing",
        current_task="",
        next_action="closing",
        previous_task=completed_task,
    )


def deliver(cycle_dir: Path, project_root: Path | None = None) -> dict[str, Any]:
    ws_path = resolve_workflow_state_path(cycle_dir)
    state = load_workflow_state(ws_path)
    session_dir = ws_path.parent

    if state["current_state"] != "Closing":
        raise ValueError(
            f"deliver requires Closing, got {state['current_state']!r}"
        )

    if project_root is None:
        raise ValueError("project_root required for deliver")

    tasks = _validate_closing_ready(session_dir)
    validate_session_worktrees_clean(session_dir)

    workspace = load_workspace(_workspace_path(session_dir))
    worktree_path = Path(workspace["worktree_path"].rstrip("/"))
    log_path = session_dir / "closing-test-log.md"
    test_result = run_test_suite(
        project_root=project_root,
        worktree_path=worktree_path,
        log_path=log_path,
    )
    if not test_result.passed:
        raise ValueError(f"test suite failed: exit_code={test_result.exit_code}")

    updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    task_count = len(tasks)
    write_passed(
        session_dir / "closing-checklist.md",
        {
            "task_count": task_count,
            "commit_ref_count": task_count,
            "tasks_done_count": task_count,
            "test_passed": True,
            "git_clean": True,
            "updated_at": updated_at,
        },
    )

    save_workflow_state(
        ws_path,
        {
            "current_state": "Delivered",
            "current_task": "",
            "current_phase": "",
        },
    )
    return _build_pointer(
        current_state="Delivered",
        current_task="",
        next_action="done",
    )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="lulu-code session pointer control")
    parser.add_argument("--cycle-dir", required=True, help="Absolute path to cycle cache directory")
    parser.add_argument(
        "--project-root",
        help="Absolute path to project root (required for deliver)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check-recovery", help="Read-only entry recovery probe")
    sub.add_parser("get-pointer", help="Read session pointer")
    confirm = sub.add_parser("confirm-task-ready", help="Validate task exit contract")
    confirm.add_argument("--task-id", required=True, help="Task id just completed (e.g. t1)")
    advance = sub.add_parser("advance-pointer", help="Advance after completed task")
    advance.add_argument("--completed-task", required=True, help="Task id just completed (e.g. t1)")
    sub.add_parser("deliver", help="Transition Closing -> Delivered")

    args = parser.parse_args()
    cycle_dir = Path(args.cycle_dir).resolve()

    try:
        if args.command == "check-recovery":
            payload = check_recovery(cycle_dir)
        elif args.command == "get-pointer":
            payload = get_pointer(cycle_dir)
        elif args.command == "confirm-task-ready":
            payload = confirm_task_ready_cmd(cycle_dir, args.task_id)
        elif args.command == "advance-pointer":
            payload = advance_pointer(cycle_dir, args.completed_task)
        elif args.command == "deliver":
            if not args.project_root:
                parser.error("deliver requires --project-root")
            payload = deliver(cycle_dir, Path(args.project_root).resolve())
        else:
            parser.error(f"unknown command: {args.command}")
    except ExitContractError as exc:
        for key, msg in exc.failures:
            print(f"exit contract failed: {key} — {msg}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
