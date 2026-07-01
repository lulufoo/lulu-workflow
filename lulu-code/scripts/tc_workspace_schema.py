#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for workspace.json.

CLI:
    python3 workspace_schema.py --schema   # print JSON schema array
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_SCHEMA: list[dict] = [
    {"field": "worktree_path", "type": "string", "required": True,
     "description": "Absolute path to the primary worktree (trailing slash)"},
    {"field": "project_root", "type": "string", "required": True,
     "description": "Absolute path to the project root"},
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


def read_workspace_file(path: Path) -> tuple[dict | None, list[str]]:
    """Read workspace.json from disk; return (data, errors). Never raises."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"cannot read file: {exc}"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, ["root must be a JSON object"]
    return data, []


def validate_workspace_semantic(data: dict, project_root: Path) -> list[str]:
    """Semantic checks beyond required fields; empty means valid."""
    errors = []
    expected_root = str(project_root.resolve())
    if data.get("project_root") != expected_root:
        errors.append(
            f"project_root mismatch: expected {expected_root!r}, "
            f"got {data.get('project_root')!r}"
        )

    worktree_path = data.get("worktree_path", "")
    if not isinstance(worktree_path, str):
        errors.append("worktree_path must be a string")
    elif not worktree_path.startswith("/"):
        errors.append("worktree_path must be an absolute path")
    elif not worktree_path.endswith("/"):
        errors.append("worktree_path must have a trailing slash")

    extra = data.get("extra_worktrees")
    if extra is not None:
        if not isinstance(extra, dict):
            errors.append("extra_worktrees must be an object")
        else:
            for repo, entry in extra.items():
                if not isinstance(entry, dict):
                    errors.append(f"extra_worktrees[{repo!r}] must be an object")
                    continue
                if "path" not in entry:
                    errors.append(f"extra_worktrees[{repo!r}] missing 'path'")
                elif not isinstance(entry["path"], str):
                    errors.append(f"extra_worktrees[{repo!r}].path must be a string")
                elif not entry["path"].startswith("/"):
                    errors.append(f"extra_worktrees[{repo!r}].path must be absolute")
                elif not entry["path"].endswith("/"):
                    errors.append(f"extra_worktrees[{repo!r}].path must have trailing slash")
                if "branch" not in entry:
                    errors.append(f"extra_worktrees[{repo!r}] missing 'branch'")

    return errors


def assess_workspace_file(path: Path, project_root: Path) -> tuple[bool, dict | None, list[str]]:
    """Explicit validity gate: read → schema → semantic. No exceptions for routing."""
    data, read_errors = read_workspace_file(path)
    if read_errors:
        return False, None, read_errors
    errors = validate_workspace(data) + validate_workspace_semantic(data, project_root)
    if errors:
        return False, data, errors
    return True, data, []


def load_workspace(path: Path) -> dict:
    """Read and validate workspace.json; raise ValueError on missing required fields."""
    data, read_errors = read_workspace_file(path)
    if read_errors:
        raise ValueError(f"workspace.json invalid ({path}): {'; '.join(read_errors)}")
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
