#!/usr/bin/env python3
"""Git CLI helpers for tech-code Python scripts.

Provides worktree existence and clean-status checks used by prepare.py and
session_control.py. Does **not** perform P1–P3 worktree creation (Agent/SKILL
responsibility).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def normalize_repo_path(path: str) -> str:
    """Return path with trailing slash removed."""
    return path.rstrip("/")


def is_worktree(path: str) -> bool:
    result = subprocess.run(
        ["git", "-C", normalize_repo_path(path), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def status_clean(path: str) -> bool:
    result = subprocess.run(
        ["git", "-C", normalize_repo_path(path), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == ""


def validate_worktrees(workspace: dict) -> None:
    worktree_path = workspace.get("worktree_path", "")
    if not worktree_path:
        raise ValueError("workspace.json missing worktree_path")
    if not is_worktree(worktree_path):
        raise ValueError(f"primary worktree is not a git worktree: {worktree_path}")

    extra = workspace.get("extra_worktrees") or {}
    for repo, info in extra.items():
        path = info.get("path", "")
        if not path:
            raise ValueError(f"extra_worktree for {repo!r} missing path")
        if not is_worktree(path):
            raise ValueError(f"extra worktree for {repo!r} is not a git worktree: {path}")


def validate_worktrees_clean(workspace: dict) -> None:
    worktree_path = workspace["worktree_path"]
    if not status_clean(worktree_path):
        raise ValueError(f"primary worktree has uncommitted changes: {worktree_path}")

    extra = workspace.get("extra_worktrees") or {}
    for repo, info in extra.items():
        path = info.get("path", "")
        if not status_clean(path):
            raise ValueError(f"extra worktree for {repo!r} has uncommitted changes: {path}")


def _load_workspace(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Git ops helpers for tech-code")
    sub = parser.add_subparsers(dest="command", required=True)

    is_wt = sub.add_parser("is-worktree", help="Check if path is inside a git worktree")
    is_wt.add_argument("--path", required=True, help="Absolute path to check")

    status = sub.add_parser("status-clean", help="Check if path has clean git status")
    status.add_argument("--path", required=True, help="Absolute path to check")

    val_wt = sub.add_parser("validate-worktrees", help="Validate workspace worktrees exist")
    val_wt.add_argument("--workspace", required=True, help="Absolute path to workspace.json")

    val_clean = sub.add_parser("validate-clean", help="Validate all workspace worktrees are clean")
    val_clean.add_argument("--workspace", required=True, help="Absolute path to workspace.json")

    args = parser.parse_args()

    try:
        if args.command == "is-worktree":
            ok = is_worktree(args.path)
        elif args.command == "status-clean":
            ok = status_clean(args.path)
        elif args.command == "validate-worktrees":
            validate_worktrees(_load_workspace(Path(args.workspace)))
            ok = True
        elif args.command == "validate-clean":
            validate_worktrees_clean(_load_workspace(Path(args.workspace)))
            ok = True
        else:
            parser.error(f"unknown command: {args.command}")
            return 1

        if not ok:
            print("check failed", file=sys.stderr)
            return 1
        print(json.dumps({"ok": True}))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_cli())
