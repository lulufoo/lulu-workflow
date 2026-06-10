#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for tasks/*/commit-ref.md.

Plain key-value format (not YAML frontmatter). CLI:
    python3 commit_ref_schema.py --schema
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCHEMA: list[dict] = [
    {"field": "task_id", "type": "string", "required": True,
     "description": "Task id matching code-task-list (e.g. t1)"},
    {"field": "branch", "type": "string", "required": True,
     "description": "Git branch name for the worktree"},
    {"field": "initial_commit", "type": "string", "required": True,
     "description": "SHA of the initial task commit"},
    {"field": "final_commit", "type": "string", "required": True,
     "description": "SHA after amend (same as initial if not amended)"},
    {"field": "commit_message", "type": "string", "required": True,
     "description": "Git commit message (may be quoted in file)"},
    {"field": "amended", "type": "bool", "required": True,
     "description": "Whether final_commit was produced via amend"},
    {"field": "recorded_at", "type": "string", "required": True,
     "description": "ISO 8601 timestamp when commit-ref was written"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}


def get_schema() -> list[dict]:
    """Return field definitions for commit-ref.md."""
    return list(_SCHEMA)


def _parse_plain_key_value(content: str) -> dict:
    """Parse plain key-value lines; supports quoted commit_message and bool amended."""
    data: dict = {}
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, _, rest = stripped.partition(":")
        key = key.strip()
        value = rest.strip()
        if key == "commit_message" and len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            data[key] = value[1:-1]
        elif key == "amended":
            if value not in ("true", "false"):
                raise ValueError(f"amended must be true or false, got {value!r}")
            data[key] = value == "true"
        else:
            data[key] = value
    return data


def load_commit_ref(path: Path) -> dict:
    """Parse commit-ref.md; raise ValueError on missing required fields."""
    if not path.exists():
        raise ValueError(f"commit-ref.md not found: {path}")
    content = path.read_text(encoding="utf-8")
    data = _parse_plain_key_value(content)
    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(f"commit-ref.md missing required fields: {', '.join(missing)} ({path})")
    return data


def validate_commit_ref(data: dict, expected_task_id: str) -> None:
    """Semantic validation for a parsed commit-ref dict."""
    if data.get("task_id") != expected_task_id:
        raise ValueError(
            f"task_id mismatch: expected {expected_task_id!r}, got {data.get('task_id')!r}"
        )
    if not data.get("initial_commit"):
        raise ValueError("initial_commit must be non-empty")
    if not data.get("final_commit"):
        raise ValueError("final_commit must be non-empty")
    if not isinstance(data.get("amended"), bool):
        raise ValueError("amended must be a boolean")
    if not data.get("recorded_at"):
        raise ValueError("recorded_at must be non-empty")


def validate_session_commit_refs(session_dir: Path, tasks: list[dict]) -> None:
    """Validate all task commit-refs exist, match task list, and reject orphans."""
    tasks_dir = session_dir / "tasks"
    task_ids = {t["id"] for t in tasks}
    commit_ref_count = 0

    for task in tasks:
        ref_path = tasks_dir / task["id"] / "commit-ref.md"
        data = load_commit_ref(ref_path)
        validate_commit_ref(data, task["id"])
        commit_ref_count += 1

    if tasks_dir.is_dir():
        for child in tasks_dir.iterdir():
            if not child.is_dir():
                continue
            ref_path = child / "commit-ref.md"
            if ref_path.exists() and child.name not in task_ids:
                raise ValueError(
                    f"orphan commit-ref.md for task not in code-task-list: {child.name}"
                )

    if len(tasks) != commit_ref_count:
        raise ValueError(
            f"commit-ref count {commit_ref_count} does not match task count {len(tasks)}"
        )


def _cli() -> int:
    parser = argparse.ArgumentParser(description="commit-ref.md schema utilities")
    parser.add_argument("--schema", action="store_true", help="Print JSON schema array and exit")
    args = parser.parse_args()
    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
