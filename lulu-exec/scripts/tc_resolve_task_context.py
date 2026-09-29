#!/usr/bin/env python3
"""Resolve paths and config for task-runner dispatch input (library module).

Imported by task_control.py resolve-context subcommand.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from stage_identity import EXEC_STAGE  # noqa: E402
from workflow_config_schema import extract_subagent_model, load_stage_config  # noqa: E402
from tc_workflow_common import exec_stage_dir  # noqa: E402

from tc_code_task_list import parse_tdd_exempt_from_list  # noqa: E402
from tc_session_state_schema import load_session_state, load_work_order_round  # noqa: E402
from tc_task_frontmatter import (  # noqa: E402
    describe_effects,
    parse_acceptance_criteria,
    parse_kind_from_frontmatter,
    parse_tdd_exempt_from_frontmatter,
    read_task_frontmatter,
)
from tc_workspace_schema import load_workspace  # noqa: E402


def _resolve_worktree_for_task(
    *,
    workspace: dict,
    project_root: Path,
    target_repo: str,
    execution_worktree: str,
    execution_worktree_path: str,
) -> tuple[str, str]:
    """Map task frontmatter to (worktree_abs_path, branch)."""
    repos = workspace.get("repos") or {}
    if execution_worktree != "custom_path" and target_repo in repos:
        info = repos[target_repo]
        path = info.get("path", "") if isinstance(info, dict) else ""
        branch = info.get("branch", "") if isinstance(info, dict) else ""
        if path and branch:
            return path.rstrip("/"), branch

    if execution_worktree == "feature_worktree":
        path = workspace.get("worktree_path", "")
        branch = workspace.get("branch", "")
        if not path or not branch:
            raise ValueError("workspace.json missing worktree_path or branch")
        return path.rstrip("/"), branch

    if execution_worktree == "extra_repo_worktree":
        extra = workspace.get("extra_worktrees") or {}
        if target_repo not in extra:
            raise ValueError(f"extra_worktree for {target_repo!r} not found")
        info = extra[target_repo]
        path = info.get("path", "")
        branch = info.get("branch", "")
        if not path or not branch:
            raise ValueError(f"extra_worktree for {target_repo!r} missing path or branch")
        return path.rstrip("/"), branch

    if execution_worktree == "custom_path":
        if not execution_worktree_path:
            raise ValueError("missing execution_worktree_path for custom_path")
        path = Path(execution_worktree_path)
        if path.is_absolute():
            raise ValueError("execution_worktree_path must be relative")
        branch = workspace.get("branch", "")
        if not branch:
            raise ValueError("workspace.json missing branch for custom_path")
        return str((project_root / path).resolve()), branch

    raise ValueError(f"invalid execution_worktree: {execution_worktree!r}")


def _read_frontmatter_optional(task_path: Path) -> dict | None:
    if not task_path.exists():
        return None
    try:
        return read_task_frontmatter(task_path)
    except ValueError:
        return None


def _resolve_tdd_exempt(
    *,
    work_order_task_path: Path,
    code_task_list_path: Path,
    task_id: str,
) -> bool:
    """Frontmatter wins; else [tdd_exempt] on code-task-list line."""
    fm = _read_frontmatter_optional(work_order_task_path)
    if fm is not None:
        from_fm = parse_tdd_exempt_from_frontmatter(fm)
        if from_fm is not None:
            return from_fm

    if code_task_list_path.exists():
        content = code_task_list_path.read_text(encoding="utf-8")
        if parse_tdd_exempt_from_list(content, task_id):
            return True

    return False


def resolve_task_context(
    cycle_dir: Path,
    task_id: str,
    project_root: Path,
    *,
    include_model: bool = False,
) -> dict[str, Any]:
    """Resolve paths and config for task-runner dispatch input."""
    cycle_dir = cycle_dir.resolve()
    project_root = project_root.resolve()

    wo_session_state = cycle_dir / "lulu-tasks" / "session-state.md"
    code_session_state = exec_stage_dir(cycle_dir) / "session-state.md"

    for path in (wo_session_state, code_session_state):
        if not path.exists():
            raise ValueError(f"session-state.md not found: {path}")

    wo_index = f"r{load_work_order_round(wo_session_state)}"
    code_index = f"s{load_session_state(code_session_state)}"

    work_order_task_path = cycle_dir / "lulu-tasks" / wo_index / "tasks" / task_id / "task.md"
    stage_dir = exec_stage_dir(cycle_dir)
    task_output_dir = stage_dir / code_index / "tasks" / task_id
    code_task_list_path = stage_dir / code_index / "code-task-list.md"
    workspace_json_path = stage_dir / code_index / "workspace.json"

    if not workspace_json_path.exists():
        raise ValueError(f"workspace.json not found: {workspace_json_path}")

    workspace = load_workspace(workspace_json_path)

    fm = _read_frontmatter_optional(work_order_task_path)
    if fm is None:
        raise ValueError(f"task frontmatter not found or invalid: {work_order_task_path}")

    kind = parse_kind_from_frontmatter(fm)

    target_repo = str(fm.get("target_repo", ""))
    execution_worktree = str(fm.get("execution_worktree", ""))
    unbound_action = kind == "action" and not execution_worktree

    if unbound_action:
        worktree_abs_path, branch = project_root.as_posix(), ""
    else:
        if not target_repo:
            raise ValueError(f"task {task_id}: missing target_repo")
        if not execution_worktree:
            raise ValueError(f"task {task_id}: missing execution_worktree")
        worktree_abs_path, branch = _resolve_worktree_for_task(
            workspace=workspace,
            project_root=project_root,
            target_repo=target_repo,
            execution_worktree=execution_worktree,
            execution_worktree_path=str(fm.get("execution_worktree_path", "")),
        )

    code_cfg = load_stage_config(project_root, EXEC_STAGE)
    git_cfg = code_cfg.get("git", {})

    tdd_exempt = _resolve_tdd_exempt(
        work_order_task_path=work_order_task_path,
        code_task_list_path=code_task_list_path,
        task_id=task_id,
    )

    result: dict[str, Any] = {
        "task_id": task_id,
        "kind": kind,
        "work_order_task_path": str(work_order_task_path),
        "task_output_dir": str(task_output_dir),
        "code_task_list_path": str(code_task_list_path),
        "worktree_abs_path": worktree_abs_path,
        "branch": branch,
        "tdd_exempt": tdd_exempt,
        "commit_message_template": git_cfg.get("commit_message_template", ""),
        "test_command": code_cfg.get("test_command", ""),
    }

    if kind == "action":
        result["goal"] = str(fm.get("title", "")).strip()
        result["effects"] = describe_effects(fm)
        result["acceptance"] = parse_acceptance_criteria(
            work_order_task_path.read_text(encoding="utf-8")
        )

    if include_model:
        model = extract_subagent_model(code_cfg)
        if model:
            result["model"] = model

    return result
