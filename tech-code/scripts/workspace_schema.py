#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for workspace.json.

CLI:
    python3 workspace_schema.py --schema   # print JSON schema array
"""

import argparse
import json
import sys
from pathlib import Path


_SCHEMA: list[dict] = [
    {"field": "worktree_path", "type": "string", "required": True,
     "description": "Absolute path to the primary worktree (trailing slash)"},
    {"field": "project_root", "type": "string", "required": True,
     "description": "Absolute path to the project root"},
    {"field": "primary_repo", "type": "string", "required": True,
     "description": "target_repo value of the first task (may be empty string)"},
    {"field": "branch", "type": "string", "required": True,
     "description": "Git branch name for the primary worktree"},
    {"field": "created_at", "type": "string", "required": True,
     "description": "ISO 8601 creation timestamp"},
    {"field": "extra_worktrees", "type": "object", "required": False,
     "description": "Additional worktree mapping: repo -> {path, branch}"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}


def get_schema() -> list[dict]:
    """Return field definitions for workspace.json."""
    return list(_SCHEMA)


def validate_workspace(data: dict) -> list[str]:
    """Return list of validation error strings; empty means valid."""
    errors = []
    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")
    return errors


def load_workspace(path: Path) -> dict:
    """Read and validate workspace.json; raise ValueError on missing required fields."""
    data = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_workspace(data)
    if errors:
        raise ValueError(f"workspace.json invalid ({path}): {'; '.join(errors)}")
    return data


def save_workspace(path: Path, data: dict) -> None:
    """Write data to workspace.json, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _cli() -> int:
    p = argparse.ArgumentParser(description="workspace.json schema utilities")
    p.add_argument("--schema", action="store_true", help="Print JSON schema array and exit")
    args = p.parse_args()
    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
