#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for s{N}/repo-map.json.

CLI:
    python3 tc_repo_map_schema.py --schema
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


_SCHEMA: list[dict] = [
    {"field": "version", "type": "int", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "binds", "type": "object", "required": True,
     "description": "target_repo name -> absolute checkout path"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}


def get_schema() -> list[dict]:
    """Return field definitions for repo-map.json."""
    return list(_SCHEMA)


def repo_map_path(session_dir: Path) -> Path:
    """Return the canonical path for s{N}/repo-map.json."""
    return session_dir / "repo-map.json"


def validate_repo_map(data: dict) -> list[str]:
    """Return validation errors; empty means valid."""
    errors: list[str] = []
    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")
    version = data.get("version")
    if "version" in data and version != 1:
        errors.append("version must be 1")
    binds = data.get("binds")
    if binds is None:
        return errors
    if not isinstance(binds, dict):
        errors.append("binds must be an object")
        return errors
    for name, path in binds.items():
        if not isinstance(name, str) or not name.strip():
            errors.append("binds keys must be non-empty strings")
            continue
        if not isinstance(path, str) or not path.startswith("/"):
            errors.append(f"binds[{name!r}] must be an absolute path")
    return errors


def read_repo_map(path: Path) -> tuple[dict | None, list[str]]:
    """Read repo-map.json; return (data, errors). Never raises."""
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


def load_repo_map(path: Path) -> dict[str, str]:
    """Read and validate repo-map.json; raise ValueError on failure."""
    data, read_errors = read_repo_map(path)
    if read_errors:
        raise ValueError(f"repo-map.json invalid ({path}): {'; '.join(read_errors)}")
    errors = validate_repo_map(data)
    if errors:
        raise ValueError(f"repo-map.json invalid ({path}): {'; '.join(errors)}")
    binds = data["binds"]
    return {str(name): str(path) for name, path in binds.items()}


def save_repo_map(path: Path, binds: dict[str, str]) -> Path:
    """Write repo-map.json and return the path."""
    payload = {"version": 1, "binds": binds}
    errors = validate_repo_map(payload)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def required_target_repos(tasks: list[dict]) -> set[str]:
    """Return target_repo names that need a checkout bind."""
    required: set[str] = set()
    for task in tasks:
        if task.get("execution_worktree") == "custom_path":
            continue
        repo = str(task.get("target_repo") or "").strip()
        if repo:
            required.add(repo)
    return required


def missing_binds(binds: dict[str, str], tasks: list[dict]) -> list[str]:
    """Return required target_repo names not present in binds."""
    return sorted(required_target_repos(tasks) - set(binds))


def main() -> int:
    parser = argparse.ArgumentParser(description="repo-map.json schema utilities")
    parser.add_argument("--schema", action="store_true")
    args = parser.parse_args()
    if args.schema:
        print(json.dumps(get_schema(), indent=2))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
