#!/usr/bin/env python3
"""Session pointer control for tech-code orchestrator.

Subcommands:
    get-pointer       Read workflow-state and return PointerResponse JSON
    advance-pointer   Advance after a completed task
    deliver           Transition Closing -> Delivered
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from git_ops import validate_worktrees, validate_worktrees_clean  # noqa: E402
from code_task_list import (  # noqa: E402
    all_done,
    assert_task_done,
    first_pending,
    next_pending_after,
    parse_tasks,
)
from session_state_schema import load_session_state  # noqa: E402
from workflow_common import parse_frontmatter_fields  # noqa: E402
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path,
    save_workflow_state,
)
from workspace_schema import load_workspace  # noqa: E402

_UNCHECKED_RE = re.compile(r"^-\s+\[\s\]\s")


def _session_dir(cycle_dir: Path) -> Path:
    active = load_session_state(cycle_dir / "tech" / "code" / "session-state.md")
    return cycle_dir / "tech" / "code" / f"s{active}"


def _task_list_path(session_dir: Path) -> Path:
    return session_dir / "code-task-list.md"


def _workspace_path(session_dir: Path) -> Path:
    return session_dir / "workspace.json"


def _validate_closing_ready(session_dir: Path) -> None:
    task_list_path = _task_list_path(session_dir)
    if not task_list_path.exists():
        raise ValueError(f"code-task-list.md not found: {task_list_path}")

    tasks = parse_tasks(task_list_path.read_text(encoding="utf-8"))
    if not tasks:
        raise ValueError("code-task-list.md has no tasks")
    if not all_done(tasks):
        raise ValueError("not all tasks are marked done in code-task-list.md")

    for task in tasks:
        commit_ref = session_dir / "tasks" / task["id"] / "commit-ref.md"
        if not commit_ref.exists():
            raise ValueError(f"missing commit-ref.md for task {task['id']}: {commit_ref}")


def _task_is_done(task_list_path: Path, task_id: str) -> bool:
    for task in parse_tasks(task_list_path.read_text(encoding="utf-8")):
        if task["id"] == task_id:
            return task["done"]
    return False


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


def _validate_delivery_approval(session_dir: Path) -> None:
    approval_path = session_dir / "delivery-approval.md"
    if not approval_path.exists():
        raise ValueError(f"delivery-approval.md not found: {approval_path}")
    fields = parse_frontmatter_fields(approval_path.read_text(encoding="utf-8"))
    if fields.get("approved") != "true":
        raise ValueError("delivery-approval.md approved must be true")


def _validate_checklist_complete(session_dir: Path) -> None:
    checklist_path = session_dir / "closing-checklist.md"
    if not checklist_path.exists():
        raise ValueError(f"closing-checklist.md not found: {checklist_path}")
    content = checklist_path.read_text(encoding="utf-8")
    unchecked = [line for line in content.splitlines() if _UNCHECKED_RE.match(line.strip())]
    if unchecked:
        raise ValueError("closing-checklist.md has unchecked items")


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
        if not current_task:
            raise ValueError("Executing state requires current_task")
        task_list_path = _task_list_path(session_dir)
        if _task_is_done(task_list_path, current_task):
            raise ValueError(
                f"pointer drift: current_task {current_task} is already done in code-task-list.md"
            )
        return _build_pointer(
            current_state=current_state,
            current_task=current_task,
            next_action="dispatch",
        )

    if current_state == "Closing":
        _validate_closing_ready(session_dir)
        return _build_pointer(
            current_state=current_state,
            current_task="",
            next_action="closing",
        )

    if current_state == "Delivered":
        _validate_delivery_approval(session_dir)
        return _build_pointer(
            current_state=current_state,
            current_task="",
            next_action="done",
        )

    raise ValueError(f"unsupported current_state: {current_state}")


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
        return _build_pointer(
            current_state="Executing",
            current_task=next_task,
            next_action="dispatch",
            previous_task=completed_task,
        )

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

    _validate_closing_ready(session_dir)
    _validate_checklist_complete(session_dir)
    _validate_delivery_approval(session_dir)

    workspace = load_workspace(_workspace_path(session_dir))
    validate_worktrees(workspace)
    validate_worktrees_clean(workspace)

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
    parser = argparse.ArgumentParser(description="tech-code session pointer control")
    parser.add_argument("--cycle-dir", required=True, help="Absolute path to cycle cache directory")
    parser.add_argument("--project-root", help="Absolute path to project root (required for deliver)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("get-pointer", help="Read session pointer")
    advance = sub.add_parser("advance-pointer", help="Advance after completed task")
    advance.add_argument("--completed-task", required=True, help="Task id just completed (e.g. t1)")
    sub.add_parser("deliver", help="Transition Closing -> Delivered")

    args = parser.parse_args()
    cycle_dir = Path(args.cycle_dir).resolve()

    try:
        if args.command == "get-pointer":
            payload = get_pointer(cycle_dir)
        elif args.command == "advance-pointer":
            payload = advance_pointer(cycle_dir, args.completed_task)
        elif args.command == "deliver":
            if not args.project_root:
                parser.error("deliver requires --project-root")
            payload = deliver(cycle_dir, Path(args.project_root).resolve())
        else:
            parser.error(f"unknown command: {args.command}")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
