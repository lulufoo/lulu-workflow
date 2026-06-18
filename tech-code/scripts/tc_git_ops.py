#!/usr/bin/env python3
"""Git CLI helpers for tech-code Python scripts.

Provides P1–P3 worktree preparation (``prepare_worktrees``), worktree existence
and clean-status checks used by ``prepare.py`` and ``session_control.py``.
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


def run_git(cwd: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run ``git -C <cwd> <args>``; non-zero exit raises ValueError with stderr."""
    cmd = ["git", "-C", normalize_repo_path(cwd), *args]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip() or f"git failed: {' '.join(args)}"
        raise ValueError(err)
    return result


def is_worktree(path: str) -> bool:
    result = subprocess.run(
        ["git", "-C", normalize_repo_path(path), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def worktree_branch(path: str) -> str:
    """Return the current branch name for a worktree path."""
    result = run_git(path, "rev-parse", "--abbrev-ref", "HEAD")
    return result.stdout.strip()


def git_head_sha(path: str) -> str:
    """Return current HEAD commit SHA for a worktree."""
    result = run_git(path, "rev-parse", "HEAD")
    return result.stdout.strip()


def git_add_all(path: str) -> None:
    """Stage all changes in worktree."""
    run_git(path, "add", "-A")


def git_commit(path: str, message: str) -> str:
    """Create commit; return new HEAD SHA."""
    run_git(path, "commit", "-m", message)
    return git_head_sha(path)


def git_commit_amend(path: str, message: str | None = None) -> str:
    """Amend last commit; return new HEAD SHA."""
    if message:
        run_git(path, "commit", "--amend", "-m", message)
    else:
        run_git(path, "commit", "--amend", "--no-edit")
    return git_head_sha(path)


def status_clean(path: str) -> bool:
    result = subprocess.run(
        ["git", "-C", normalize_repo_path(path), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == ""


def pre_check_clean(project_root: str) -> None:
    """P1: fail if main checkout has uncommitted changes."""
    root = normalize_repo_path(project_root)
    result = subprocess.run(
        ["git", "-C", root, "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "git status failed")
    if result.stdout.strip():
        short = subprocess.run(
            ["git", "-C", root, "status", "--short"],
            capture_output=True,
            text=True,
            check=False,
        )
        detail = short.stdout.strip() if short.returncode == 0 else result.stdout.strip()
        raise ValueError(
            f"main checkout has uncommitted changes:\n{detail}"
        )


def branch_exists(project_root: str, branch: str) -> bool:
    result = subprocess.run(
        [
            "git",
            "-C",
            normalize_repo_path(project_root),
            "show-ref",
            "--verify",
            f"refs/heads/{branch}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def resolve_worktree_action(project_root: str, path: str, branch: str) -> str:
    """Return ``skip`` or ``create`` for a target worktree path/branch pair."""
    norm_path = normalize_repo_path(path)
    path_obj = Path(norm_path)

    if is_worktree(path):
        current = worktree_branch(path)
        if current == branch:
            return "skip"
        raise ValueError(
            f"worktree at {path!r} is on branch {current!r}, expected {branch!r}"
        )

    if path_obj.exists():
        raise ValueError(
            f"path exists but is not a git worktree: {path!r}"
        )

    if branch_exists(project_root, branch):
        raise ValueError(
            f"branch {branch!r} exists but worktree path is missing: {path!r}"
        )

    return "create"


def sync_repo(project_root: str) -> None:
    """P2: pull --rebase on project_root; abort rebase on conflict."""
    root = normalize_repo_path(project_root)
    result = subprocess.run(
        ["git", "-C", root, "pull", "--rebase"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        subprocess.run(
            ["git", "-C", root, "rebase", "--abort"],
            capture_output=True,
            text=True,
            check=False,
        )
        err = result.stderr.strip() or result.stdout.strip() or "pull --rebase failed"
        raise ValueError(f"sync failed: {err}")


def create_worktree(project_root: str, path: str, branch: str) -> None:
    """P3: create a new worktree with a new branch."""
    abs_path = str(Path(normalize_repo_path(path)).resolve())
    run_git(project_root, "worktree", "add", abs_path, "-b", branch)


def _collect_targets(workspace: dict) -> list[tuple[str, str]]:
    """Return list of (path, branch) for primary and extra worktrees."""
    primary_path = workspace.get("worktree_path", "")
    primary_branch = workspace.get("branch", "")
    if not primary_path or not primary_branch:
        raise ValueError("workspace.json missing worktree_path or branch")

    targets = [(primary_path, primary_branch)]
    extra = workspace.get("extra_worktrees") or {}
    for info in extra.values():
        path = info.get("path", "")
        branch = info.get("branch", "")
        if not path or not branch:
            raise ValueError("extra_worktree entry missing path or branch")
        targets.append((path, branch))
    return targets


def prepare_worktrees(project_root: str, workspace: dict) -> None:
    """Run P1–P3 for primary and extra worktrees with need_create gating for P2."""
    pre_check_clean(project_root)

    actions: list[tuple[str, str, str]] = []
    for path, branch in _collect_targets(workspace):
        action = resolve_worktree_action(project_root, path, branch)
        actions.append((path, branch, action))

    need_create = any(action == "create" for _, _, action in actions)
    if need_create:
        sync_repo(project_root)

    for path, branch, action in actions:
        if action == "create":
            create_worktree(project_root, path, branch)


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


def validate_session_worktrees_clean(session_dir: Path) -> None:
    """Validate primary and extra worktrees exist and are clean for a session."""
    from tc_workspace_schema import load_workspace

    workspace = load_workspace(session_dir / "workspace.json")
    validate_worktrees(workspace)
    validate_worktrees_clean(workspace)


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
    val_clean.add_argument("--workspace", help="Absolute path to workspace.json")
    val_clean.add_argument("--session-dir", help="Absolute path to session dir (uses workspace.json inside)")

    val_session = sub.add_parser(
        "validate-session-clean",
        help="Validate session worktrees exist and are clean",
    )
    val_session.add_argument("--session-dir", required=True, help="Absolute path to session dir")

    prep = sub.add_parser("prepare-worktrees", help="Run P1–P3 for a workspace.json")
    prep.add_argument("--project-root", required=True, help="Absolute path to project root")
    prep.add_argument("--workspace", required=True, help="Absolute path to workspace.json")

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
            if args.session_dir:
                validate_session_worktrees_clean(Path(args.session_dir))
            elif args.workspace:
                validate_worktrees_clean(_load_workspace(Path(args.workspace)))
            else:
                parser.error("validate-clean requires --workspace or --session-dir")
            ok = True
        elif args.command == "validate-session-clean":
            validate_session_worktrees_clean(Path(args.session_dir))
            ok = True
        elif args.command == "prepare-worktrees":
            prepare_worktrees(args.project_root, _load_workspace(Path(args.workspace)))
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
