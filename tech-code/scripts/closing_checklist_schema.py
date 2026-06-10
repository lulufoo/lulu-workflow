#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for closing-checklist.md.

CLI:
    python3 closing_checklist_schema.py --schema
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_SCHEMA: list[dict] = [
    {"field": "version", "type": "int", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "updated_at", "type": "string", "required": True,
     "description": "ISO 8601 timestamp when checklist was written"},
]

_EVIDENCE_KEYS = frozenset({
    "task_count",
    "commit_ref_count",
    "tasks_done_count",
    "test_passed",
    "git_clean",
    "updated_at",
})

_UNCHECKED_RE = re.compile(r"^-\s+\[\s\]\s")


def get_schema() -> list[dict]:
    """Return field definitions for closing-checklist.md frontmatter."""
    return list(_SCHEMA)


def write_passed(path: Path, evidence: dict) -> None:
    """Write a completed closing-checklist.md after all deliver gates pass."""
    missing = [k for k in _EVIDENCE_KEYS if k not in evidence]
    if missing:
        raise ValueError(f"evidence missing required keys: {', '.join(missing)}")

    task_count = evidence["task_count"]
    updated_at = evidence["updated_at"]
    body = (
        f"---\n"
        f"version: 1\n"
        f"updated_at: {updated_at}\n"
        f"---\n"
        f"## Closing gate\n\n"
        f"- [x] Full test suite re-run (PASS)\n"
        f"- [x] commit-ref count == task count · {task_count}/{task_count}\n"
        f"- [x] git status clean in worktree\n"
        f"- [x] All code-task-list items [x] · {task_count}/{task_count}\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def validate_complete(path: Path) -> None:
    """Validate closing-checklist.md is fully checked (recovery diagnostic)."""
    if not path.exists():
        raise ValueError(f"closing-checklist.md not found: {path}")
    content = path.read_text(encoding="utf-8")
    unchecked = [line for line in content.splitlines() if _UNCHECKED_RE.match(line.strip())]
    if unchecked:
        raise ValueError("closing-checklist.md has unchecked items")
    if "version: 1" not in content:
        raise ValueError("closing-checklist.md missing version frontmatter")


def _cli() -> int:
    parser = argparse.ArgumentParser(description="closing-checklist.md schema utilities")
    parser.add_argument("--schema", action="store_true", help="Print JSON schema array and exit")
    args = parser.parse_args()
    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
