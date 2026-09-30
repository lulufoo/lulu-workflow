#!/usr/bin/env python3
"""Parse and query lulu-exec code-task-list.md task checkboxes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

_TASK_LINE_RE = re.compile(
    r"^-\s+\[(?P<done>[ xX])\]\s+(?P<id>t\d+[a-z]*)\b(?:\s+·\s+(?P<title>[^·\n]+))?"
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


def parse_task_title(content: str, task_id: str) -> str | None:
    """Return title segment from code-task-list line for task_id, or None."""
    for line in content.splitlines():
        match = _TASK_LINE_RE.match(line.strip())
        if match and match.group("id") == task_id:
            title = match.group("title")
            return title.strip() if title else None
    return None


def parse_tdd_exempt_from_list(content: str, task_id: str) -> bool:
    """Return True if the task line contains [tdd_exempt]."""
    for line in content.splitlines():
        match = _TASK_LINE_RE.match(line.strip())
        if match and match.group("id") == task_id:
            return "[tdd_exempt]" in line
    return False


def mark_task_done(path: Path, task_id: str) -> None:
    """Flip task checkbox to [x] in code-task-list.md."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    updated = False
    for i, line in enumerate(lines):
        match = _TASK_LINE_RE.match(line.strip())
        if match and match.group("id") == task_id:
            if match.group("done").lower() == "x":
                return
            lines[i] = re.sub(
                r"^(-\s+\[)[ xX](\])",
                r"\1x\2",
                line,
                count=1,
            )
            updated = True
            break
    if not updated:
        raise ValueError(f"task {task_id} not found in {path}")
    path.write_text("\n".join(lines) + ("\n" if content.endswith("\n") else ""), encoding="utf-8")


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
