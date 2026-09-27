#!/usr/bin/env python3
"""Validate and write one task-list.md."""

from __future__ import annotations

import re
from pathlib import Path

_REQUIRED = ("version", "work_order_round", "tech_ref", "total_tasks")
_SECTIONS = (
    "## Section 1: Task List",
    "## Section 2: Dependency Graph",
    "## Section 3: Exclusions",
)


def task_list_file(doc_dir: Path) -> Path:
    return doc_dir / "task-list.md"


def validate_task_list(body: str) -> None:
    match = re.match(r"^---\s*\n(.*?)\n---", body, re.DOTALL)
    if not match:
        raise ValueError("task-list.md is missing frontmatter")
    frontmatter = match.group(1)
    for key in _REQUIRED:
        if not re.search(rf"(?m)^{key}:\s*\S", frontmatter):
            raise ValueError(f"task-list.md is missing {key}")
    for heading in _SECTIONS:
        if heading not in body:
            raise ValueError(f"task-list.md is missing {heading}")


def write_task_list(path: Path, body: str) -> None:
    validate_task_list(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
