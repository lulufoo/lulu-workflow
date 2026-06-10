#!/usr/bin/env python3
"""Parse and query tech-code code-task-list.md task checkboxes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

_TASK_LINE_RE = re.compile(
    r"^-\s+\[(?P<done>[ xX])\]\s+(?P<id>t\d+[a-z]*)\b"
)


class TaskEntry(TypedDict):
    id: str
    done: bool


def parse_tasks(content: str) -> list[TaskEntry]:
    """Parse task checkbox lines from code-task-list.md body."""
    tasks: list[TaskEntry] = []
    for line in content.splitlines():
        match = _TASK_LINE_RE.match(line.strip())
        if not match:
            continue
        tasks.append(
            {
                "id": match.group("id"),
                "done": match.group("done").lower() == "x",
            }
        )
    return tasks


def first_pending(tasks: list[TaskEntry]) -> str | None:
    """Return the first task id that is not done, or None."""
    for task in tasks:
        if not task["done"]:
            return task["id"]
    return None


def next_pending_after(tasks: list[TaskEntry], completed_id: str) -> str | None:
    """Return the first pending task after completed_id, or None."""
    seen_completed = False
    for task in tasks:
        if task["id"] == completed_id:
            seen_completed = True
            continue
        if seen_completed and not task["done"]:
            return task["id"]
    return None


def all_done(tasks: list[TaskEntry]) -> bool:
    """Return True when every parsed task is done (empty list is True)."""
    return bool(tasks) and all(task["done"] for task in tasks)


def assert_task_done(path: Path, task_id: str) -> None:
    """Raise ValueError if task_id is missing or not marked [x]."""
    content = path.read_text(encoding="utf-8")
    tasks = parse_tasks(content)
    for task in tasks:
        if task["id"] == task_id:
            if not task["done"]:
                raise ValueError(f"task {task_id} is not marked done in {path}")
            return
    raise ValueError(f"task {task_id} not found in {path}")
