#!/usr/bin/env python3
"""Repo checkout map control for lulu-code Preparing.

Subcommands:
    list-candidates   List $PROJECT_ROOT (if git) and sibling git checkouts
    put-map           Persist target_repo -> checkout binds for s{N}

Stdin for put-map: JSON object of binds, or {"binds": {...}}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tc_repo_map_schema import (
    load_repo_map,
    repo_map_path,
    save_repo_map,
)
from tc_session_state_schema import load_session_state
from tc_workflow_common import exec_stage_dir


def is_git_checkout(path: Path) -> bool:
    """True when path has a .git directory or file."""
    return (path / ".git").exists()


def list_candidates(project_root: Path) -> list[dict[str, str]]:
    """Return unique git checkouts: project root, then sibling directories."""
    root = project_root.resolve()
    seen: set[Path] = set()
    out: list[dict[str, str]] = []

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_dir() or not is_git_checkout(resolved):
            return
        seen.add(resolved)
        out.append({"name": resolved.name, "path": resolved.as_posix()})

    add(root)
    parent = root.parent
    if parent.is_dir():
        for child in sorted(parent.iterdir()):
            if child.is_dir():
                add(child)
    return out


def _session_dir(cycle_dir: Path) -> Path:
    stage_dir = exec_stage_dir(cycle_dir)
    active = load_session_state(stage_dir / "session-state.md")
    return stage_dir / f"s{active}"


def _parse_binds(raw: str) -> dict[str, str]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"put-map stdin is not JSON: {exc}") from exc
    if isinstance(data, dict) and isinstance(data.get("binds"), dict):
        data = data["binds"]
    if not isinstance(data, dict):
        raise ValueError("put-map stdin must be an object of binds")
    binds: dict[str, str] = {}
    for name, path in data.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("bind names must be non-empty strings")
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError(f"bind {name!r} must be an absolute path")
        binds[name] = str(Path(path).resolve())
    if not binds:
        raise ValueError("put-map requires at least one bind")
    return binds


def _candidate_paths(project_root: Path) -> set[str]:
    return {item["path"] for item in list_candidates(project_root)}


def put_map(cycle_dir: Path, project_root: Path, binds: dict[str, str]) -> dict:
    """Validate binds against candidates and write repo-map.json."""
    allowed = _candidate_paths(project_root)
    unknown = [
        f"{name}={path}"
        for name, path in binds.items()
        if path not in allowed
    ]
    if unknown:
        raise ValueError(
            "bind checkout is not a listed candidate: " + "; ".join(unknown)
        )
    dest = repo_map_path(_session_dir(cycle_dir))
    save_repo_map(dest, binds)
    return {"ok": True, "binds": load_repo_map(dest)}


def cmd_list_candidates(project_root: Path) -> int:
    print(json.dumps({"candidates": list_candidates(project_root)}, indent=2))
    return 0


def cmd_put_map(cycle_dir: Path, project_root: Path) -> int:
    raw = sys.stdin.read()
    binds = _parse_binds(raw)
    payload = put_map(cycle_dir, project_root, binds)
    print(json.dumps(payload, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="lulu-code repo map control")
    parser.add_argument("--cycle-dir", type=Path)
    parser.add_argument("--project-root", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list-candidates")
    sub.add_parser("put-map")
    args = parser.parse_args()

    project_root = args.project_root.resolve()
    try:
        if args.command == "list-candidates":
            return cmd_list_candidates(project_root)
        if args.cycle_dir is None:
            raise ValueError("--cycle-dir is required for put-map")
        return cmd_put_map(args.cycle_dir.resolve(), project_root)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
