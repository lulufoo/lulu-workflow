#!/usr/bin/env python3
"""Resolve paths and config for task-runner dispatch input (library module).

Imported by session_control.py resolve-task-context subcommand only.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from session_state_schema import load_session_state, load_work_order_round
from workspace_schema import load_workspace


def resolve_task_context(cycle_dir: Path, task_id: str, project_root: Path) -> dict[str, Any]:
    """Resolve paths and config for task-runner dispatch input."""
    cycle_dir = cycle_dir.resolve()
    project_root = project_root.resolve()

    wo_session_state = cycle_dir / "tech" / "work-order" / "session-state.md"
    code_session_state = cycle_dir / "tech" / "code" / "session-state.md"

    for path in (wo_session_state, code_session_state):
        if not path.exists():
            raise ValueError(f"session-state.md not found: {path}")

    wo_index = f"r{load_work_order_round(wo_session_state)}"
    code_index = f"s{load_session_state(code_session_state)}"

    work_order_task_path = cycle_dir / "tech" / "work-order" / wo_index / "tasks" / task_id / "task.md"
    task_output_dir = cycle_dir / "tech" / "code" / code_index / "tasks" / task_id
    code_task_list_path = cycle_dir / "tech" / "code" / code_index / "code-task-list.md"
    workspace_json_path = cycle_dir / "tech" / "code" / code_index / "workspace.json"

    if not workspace_json_path.exists():
        raise ValueError(f"workspace.json not found: {workspace_json_path}")

    workspace = load_workspace(workspace_json_path)
    worktree_path = Path(workspace["worktree_path"])

    config_path = project_root / "skill-config" / "lulu-dev-workflow" / "workflow-config.json"
    if not config_path.exists():
        raise ValueError(f"workflow-config.json not found: {config_path}")

    config = json.loads(config_path.read_text(encoding="utf-8"))
    code_cfg = config.get("tech-code", {})
    git_cfg = code_cfg.get("git", {})

    return {
        "task_id": task_id,
        "work_order_task_path": str(work_order_task_path),
        "task_output_dir": str(task_output_dir),
        "code_task_list_path": str(code_task_list_path),
        "worktree_abs_path": str(worktree_path),
        "commit_message_template": git_cfg.get("commit_message_template", ""),
        "test_command": code_cfg.get("test_command", ""),
    }
