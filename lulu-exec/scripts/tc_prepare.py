#!/usr/bin/env python3
"""Prepare a new lulu-exec session: validate tasks, ensure workspace.json,
run git P1–P3, and transition Preparing -> Executing.

Usage:
    python3 prepare.py \\
        --cycle-dir /abs/path/.cache/cursor/lulu-workflow/<cycle_id> \\
        --project-root /abs/path/to/project

    python3 prepare.py ... --validate   # recovery / idempotent query only

Outputs JSON to stdout on success:
    { current_state, current_task, worktree_path, slug, branch }

Slug is auto-derived on first create: last 8 chars of cycle_id + 4-char random hex.
Requires s{N}/repo-map.json binds before creating worktrees. Create from each
bound checkout, not from --project-root unless that path is the bound checkout.
If s{N}/workspace.json already exists, matches the binds, and passes validation,
it is loaded only (created_at is not rewritten). Stale or invalid files are
deleted and recreated with a new slug.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tc_code_task_list import first_pending, parse_tasks  # noqa: E402
from tc_git_ops import prepare_worktrees, validate_worktrees  # noqa: E402
from tc_session_state_schema import load_session_state, load_work_order_round  # noqa: E402
from tc_workflow_common import (  # noqa: E402
    exec_stage_dir,
    load_stage_config,
    workflow_config_is_present,
)
from stage_identity import EXEC_STAGE  # noqa: E402
from tc_workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path,
    save_workflow_state,
)
from tc_repo_map_schema import (  # noqa: E402
    load_repo_map,
    missing_binds,
    repo_map_path,
    required_target_repos,
)
from tc_task_frontmatter import (  # noqa: E402
    TASK_KINDS,
    read_task_frontmatter,
    validate_effects,
)
from tc_workspace_schema import assess_workspace_file, load_workspace, save_workspace  # noqa: E402


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

_EXIT_CONTRACT_KEYS = {"commit", "commit_ref_md", "code_log"}
_EXECUTION_WORKTREE_VALUES = {"feature_worktree", "extra_repo_worktree", "custom_path"}


def _validate_single_task(task_id: str, fm: dict) -> list:
    """Return list of error strings; empty list means valid."""
    errors = []

    kind = str(fm.get("kind", "coding")).strip() or "coding"
    if kind not in TASK_KINDS:
        return [f"{task_id}: kind must be one of {list(TASK_KINDS)}, got '{kind}'"]
    if kind == "action":
        errors.extend(validate_effects(task_id, fm))

    ew = fm.get("execution_worktree", "")
    if not ew:
        if kind == "coding":
            errors.append(f"{task_id}: missing execution_worktree")
    elif ew not in _EXECUTION_WORKTREE_VALUES:
        errors.append(
            f"{task_id}: execution_worktree must be one of "
            f"{sorted(_EXECUTION_WORKTREE_VALUES)}, got '{ew}'"
        )

    if ew == "custom_path":
        ewp = fm.get("execution_worktree_path", "")
        if not ewp:
            errors.append(f"{task_id}: missing execution_worktree_path for custom_path")
        elif Path(ewp).is_absolute():
            errors.append(
                f"{task_id}: execution_worktree_path must be relative, got '{ewp}'"
            )

    if kind == "action" and ew and not fm.get("target_repo"):
        errors.append(f"{task_id}: missing target_repo for execution_worktree")

    ec = fm.get("exit_contract")
    if not isinstance(ec, dict):
        errors.append(f"{task_id}: missing exit_contract block")
    elif kind == "action":
        if ec.get("receipt") != "required":
            errors.append(
                f"{task_id}: exit_contract.receipt must be 'required', got '{ec.get('receipt')}'"
            )
    else:
        for key in _EXIT_CONTRACT_KEYS:
            if ec.get(key) != "required":
                errors.append(
                    f"{task_id}: exit_contract.{key} must be 'required', got '{ec.get(key)}'"
                )

    return errors


def validate_tasks(cycle_dir: Path) -> list:
    """Validate all task.md files; return normalized task execution records."""
    wo_ss = cycle_dir / "lulu-tasks" / "session-state.md"
    if not wo_ss.exists():
        print(f"Error: work-order session-state.md not found: {wo_ss}", file=sys.stderr)
        sys.exit(1)

    try:
        wo_active = load_work_order_round(wo_ss)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    tasks_dir = cycle_dir / "lulu-tasks" / f"r{wo_active}" / "tasks"
    task_files = sorted(tasks_dir.glob("*/task.md"))
    if not task_files:
        print(f"Error: no task.md files found under {tasks_dir}", file=sys.stderr)
        sys.exit(1)

    all_errors = []
    task_records = []
    for task_path in task_files:
        task_id = task_path.parent.name
        try:
            fm = read_task_frontmatter(task_path)
        except ValueError as e:
            all_errors.append(str(e))
            continue
        all_errors.extend(_validate_single_task(task_id, fm))
        bound = bool(fm.get("execution_worktree"))
        task_records.append({
            "task_id": task_id,
            "target_repo": fm.get("target_repo", "") if bound else "",
            "execution_worktree": fm.get("execution_worktree", ""),
            "execution_worktree_path": fm.get("execution_worktree_path", ""),
        })

    if all_errors:
        for err in all_errors:
            print(f"Schema error: {err}", file=sys.stderr)
        sys.exit(1)

    repo_worktree: dict = {}
    for rec in task_records:
        repo = rec["target_repo"]
        if not repo:
            continue
        execution_key = (rec["execution_worktree"], rec["execution_worktree_path"])
        if repo in repo_worktree and repo_worktree[repo] != execution_key:
            print(
                f"Schema conflict: tasks targeting '{repo}' use different worktrees: "
                f"'{repo_worktree[repo]}' vs '{execution_key}'",
                file=sys.stderr,
            )
            sys.exit(1)
        repo_worktree[repo] = execution_key

    return task_records


# ---------------------------------------------------------------------------
# Config + paths
# ---------------------------------------------------------------------------

def load_git_config(project_root: Path) -> dict:
    """Read lulu-exec.git from stage workflow config."""
    if not workflow_config_is_present(project_root):
        raise FileNotFoundError(
            f"workflow-config not found under {project_root.as_posix()}"
        )
    code_cfg = load_stage_config(project_root, EXEC_STAGE)
    return code_cfg.get("git", {})


def _derive_slug(cycle_id: str) -> str:
    """Generate a unique slug: last 8 chars of cycle_id + 4-char random hex."""
    short = cycle_id[-8:] if len(cycle_id) >= 8 else cycle_id
    suffix = secrets.token_hex(2)  # 4 hex chars
    return f"{short}-{suffix}"


def build_worktree_paths(slug: str, git_cfg: dict) -> dict:
    """Derive relative worktree_dir and branch from slug and config."""
    worktree_base = git_cfg.get("worktree_base", ".cache/worktrees")
    branch_pattern = git_cfg.get("branch_pattern", "wt/{type}-{slug}")
    default_type = git_cfg.get("default_type", "feat")
    return {
        "worktree_dir": f"{worktree_base}/{slug}/",
        "branch": branch_pattern.format(type=default_type, slug=slug),
    }


# ---------------------------------------------------------------------------
# Write workspace.json
# ---------------------------------------------------------------------------

def write_workspace(
    cycle_dir: Path,
    session_idx: int,
    slug: str,
    paths: dict,
    tasks: list,
    project_root: Path,
    repo_map: dict | None = None,
) -> Path:
    """Write s{N}/workspace.json and return the written path."""
    worktree_path = (project_root / paths["worktree_dir"]).resolve().as_posix().rstrip("/") + "/"
    payload: dict = {
        "worktree_path": worktree_path,
        "project_root": str(project_root.resolve()),
        "branch": paths["branch"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    extra: dict[str, dict] = {}
    repos: dict[str, dict] = {}
    base = paths["worktree_dir"].rstrip("/")
    primary_repo: str | None = None
    for task in tasks:
        if task.get("execution_worktree") == "custom_path":
            continue
        repo = task.get("target_repo", "")
        if not repo or repo in repos:
            continue
        if primary_repo is None:
            primary_repo = repo
            entry = {"path": worktree_path, "branch": paths["branch"]}
        else:
            suffix = repo.replace("/", "-")
            rel_path = f"{base}-{suffix}/"
            dest = (project_root / rel_path).resolve().as_posix().rstrip("/") + "/"
            branch = f"{paths['branch']}-{suffix}"
            entry = {"path": dest, "branch": branch}
            extra[repo] = {"path": dest, "branch": branch}
        if repo_map and repo in repo_map:
            entry["checkout"] = str(Path(repo_map[repo]).resolve())
        repos[repo] = entry
    if extra:
        payload["extra_worktrees"] = extra
    if repos:
        payload["repos"] = repos

    dest = exec_stage_dir(cycle_dir) / f"s{session_idx}" / "workspace.json"
    save_workspace(dest, payload)
    return dest


def _workspace_dest(cycle_dir: Path, session_idx: int) -> Path:
    """Return the canonical path for s{N}/workspace.json."""
    return exec_stage_dir(cycle_dir) / f"s{session_idx}" / "workspace.json"


def _create_workspace(
    cycle_dir: Path,
    session_idx: int,
    cycle_id: str,
    tasks: list,
    project_root: Path,
    git_cfg: dict,
    repo_map: dict | None = None,
) -> tuple[Path, dict, str, str, bool]:
    """First-time workspace creation: derive slug, write file, return created=True."""
    slug = _derive_slug(cycle_id)
    paths = build_worktree_paths(slug, git_cfg)
    dest = write_workspace(
        cycle_dir, session_idx, slug, paths, tasks, project_root, repo_map=repo_map
    )
    workspace = load_workspace(dest)
    return dest, workspace, slug, paths["branch"], True


def _workspace_matches_binds(workspace: dict, binds: dict, tasks: list) -> bool:
    """True when every required target_repo records the bound checkout."""
    repos = workspace.get("repos") or {}
    for repo in required_target_repos(tasks):
        info = repos.get(repo)
        if not isinstance(info, dict) or not info.get("checkout"):
            return False
        if Path(info["checkout"]).resolve() != Path(binds[repo]).resolve():
            return False
    return True


def ensure_workspace(
    cycle_dir: Path,
    session_idx: int,
    cycle_id: str,
    tasks: list,
    project_root: Path,
    git_cfg: dict,
    repo_map: dict | None = None,
) -> tuple[Path, dict, str, str, bool]:
    """Load valid workspace.json without writing; delete and recreate if invalid."""
    dest = _workspace_dest(cycle_dir, session_idx)
    if dest.exists():
        ok, workspace, errors = assess_workspace_file(dest, project_root)
        if ok and (repo_map is None or _workspace_matches_binds(workspace, repo_map, tasks)):
            slug = Path(workspace["worktree_path"].rstrip("/")).name
            return dest, workspace, slug, workspace["branch"], False
        if not ok:
            print(f"workspace.json invalid, recreating: {errors}", file=sys.stderr)
        else:
            print("workspace.json checkout map stale, recreating", file=sys.stderr)
        dest.unlink(missing_ok=True)

    return _create_workspace(
        cycle_dir, session_idx, cycle_id, tasks, project_root, git_cfg, repo_map=repo_map
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def validate_preparing_to_executing(cycle_dir: Path) -> dict:
    """Transition Preparing -> Executing after worktree validation."""
    ws_path = resolve_workflow_state_path(cycle_dir)
    state = load_workflow_state(ws_path)
    session_dir = ws_path.parent
    workspace_path = session_dir / "workspace.json"

    if state["current_state"] == "Executing":
        current_task = state.get("current_task", "")
        task_list_path = session_dir / "code-task-list.md"
        tasks = parse_tasks(task_list_path.read_text(encoding="utf-8"))
        task_ids = {task["id"] for task in tasks}
        if current_task and current_task in task_ids:
            workspace = load_workspace(workspace_path)
            return {
                "current_state": "Executing",
                "current_task": current_task,
                "worktree_path": workspace.get("worktree_path", ""),
            }
        raise ValueError(
            f"Executing state has invalid current_task {current_task!r}"
        )

    if state["current_state"] != "Preparing":
        raise ValueError(
            f"--validate requires Preparing or idempotent Executing, got {state['current_state']!r}"
        )

    if not workspace_path.exists():
        raise ValueError(f"workspace.json not found: {workspace_path}")

    workspace = load_workspace(workspace_path)
    validate_worktrees(workspace)

    task_list_path = session_dir / "code-task-list.md"
    if not task_list_path.exists():
        raise ValueError(f"code-task-list.md not found: {task_list_path}")

    tasks = parse_tasks(task_list_path.read_text(encoding="utf-8"))
    first_task = first_pending(tasks)
    if not first_task:
        raise ValueError("no pending tasks in code-task-list.md")

    save_workflow_state(
        ws_path,
        {
            "current_state": "Executing",
            "current_task": first_task,
            "current_phase": "",
        },
    )
    return {
        "current_state": "Executing",
        "current_task": first_task,
        "worktree_path": workspace.get("worktree_path", ""),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Prepare lulu-exec session workspace.")
    p.add_argument("--cycle-dir", required=True, help="Absolute path to cycle cache directory.")
    p.add_argument("--project-root", required=True, help="Absolute path to project root.")
    p.add_argument(
        "--validate",
        action="store_true",
        help="Validate worktrees and transition Preparing -> Executing.",
    )
    return p.parse_known_args()[0]


def _enrich_payload(payload: dict, cycle_dir: Path, slug: str, branch: str) -> dict:
    """Add slug/branch to stdout payload from workspace.json when available."""
    result = {**payload, "slug": slug, "branch": branch}
    if slug and branch:
        return result
    ws_path = resolve_workflow_state_path(cycle_dir).parent / "workspace.json"
    if ws_path.exists():
        workspace = load_workspace(ws_path)
        if not slug:
            wt = workspace.get("worktree_path", "")
            if wt:
                result["slug"] = Path(wt.rstrip("/")).name
        if not branch:
            result["branch"] = workspace.get("branch", branch)
    return result


def main() -> int:
    args = parse_args()
    cycle_dir = Path(args.cycle_dir).resolve()
    project_root = Path(args.project_root).resolve()
    cycle_id = cycle_dir.name

    if args.validate:
        try:
            payload = validate_preparing_to_executing(cycle_dir)
            ws_path = resolve_workflow_state_path(cycle_dir).parent / "workspace.json"
            slug = ""
            branch = ""
            if ws_path.exists():
                workspace = load_workspace(ws_path)
                wt = workspace.get("worktree_path", "")
                slug = Path(wt.rstrip("/")).name if wt else ""
                branch = workspace.get("branch", "")
            payload = _enrich_payload(payload, cycle_dir, slug, branch)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    tasks = validate_tasks(cycle_dir)

    try:
        git_cfg = load_git_config(project_root)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        session_idx = load_session_state(exec_stage_dir(cycle_dir) / "session-state.md")
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    map_path = repo_map_path(exec_stage_dir(cycle_dir) / f"s{session_idx}")
    try:
        binds = load_repo_map(map_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    missing = missing_binds(binds, tasks)
    if missing:
        print(f"repo-map missing binds for: {', '.join(missing)}", file=sys.stderr)
        return 1

    dest, workspace, slug, branch, created = ensure_workspace(
        cycle_dir, session_idx, cycle_id, tasks, project_root, git_cfg, repo_map=binds
    )

    try:
        prepare_worktrees(str(project_root), workspace)
        result = validate_preparing_to_executing(cycle_dir)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = _enrich_payload(result, cycle_dir, slug, branch)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
