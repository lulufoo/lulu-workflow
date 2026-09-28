#!/usr/bin/env python3
"""Validate and write one tasks/tN/task.md. Frontmatter only."""

from __future__ import annotations

import re
from pathlib import Path

_VALUES = (
    "version",
    "task_id",
    "title",
    "tdd_exempt",
    "target_repo",
    "execution_worktree",
)
_KEYS = ("target_files", "dependencies")
_WORKTREES = {"feature_worktree", "extra_repo_worktree", "custom_path"}
_KINDS = {"coding", "verify"}
_EXIT_KEYS = ("commit", "commit_ref_md", "code_log")


def task_file(doc_dir: Path, task_id: str) -> Path:
    return doc_dir / "tasks" / task_id / "task.md"


def _frontmatter(body: str) -> str:
    match = re.match(r"^---\s*\n(.*?)\n---", body, re.DOTALL)
    if not match:
        raise ValueError("task.md is missing frontmatter")
    return match.group(1)


def task_id_of(body: str) -> str:
    frontmatter = _frontmatter(body)
    match = re.search(r"(?m)^task_id:\s*(\S+)\s*$", frontmatter)
    if not match or not re.fullmatch(r"t[1-9]\d*", match.group(1)):
        raise ValueError("task_id must look like t1")
    return match.group(1)


def validate_task(body: str) -> str:
    frontmatter = _frontmatter(body)
    for key in _VALUES:
        if not re.search(rf"(?m)^{key}:\s*\S", frontmatter):
            raise ValueError(f"task.md is missing {key}")
    for key in _KEYS:
        if not re.search(rf"(?m)^{key}:", frontmatter):
            raise ValueError(f"task.md is missing {key}")
    kind = re.search(r"(?m)^kind:\s*(\S+)\s*$", frontmatter)
    if kind is None:
        raise ValueError("task.md is missing kind")
    if kind.group(1) not in _KINDS:
        raise ValueError("kind must be coding or verify")
    worktree = re.search(r"(?m)^execution_worktree:\s*(\S+)\s*$", frontmatter)
    if worktree is None or worktree.group(1) not in _WORKTREES:
        raise ValueError("execution_worktree is not a known value")
    if worktree.group(1) == "custom_path" and not re.search(
        r"(?m)^execution_worktree_path:\s*\S",
        frontmatter,
    ):
        raise ValueError("task.md is missing execution_worktree_path")
    if not re.search(r"(?m)^exit_contract:\s*$", frontmatter):
        raise ValueError("task.md is missing exit_contract")
    for key in _EXIT_KEYS:
        if not re.search(rf"(?m)^  {key}:\s*required\s*$", frontmatter):
            raise ValueError(f"exit_contract.{key} must be required")
    return task_id_of(body)


def write_task(doc_dir: Path, body: str) -> Path:
    task_id = validate_task(body)
    path = task_file(doc_dir, task_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body if body.endswith("\n") else body + "\n", encoding="utf-8")
    return path
