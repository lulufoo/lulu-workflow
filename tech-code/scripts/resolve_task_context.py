#!/usr/bin/env python3
"""Resolve all file paths needed by a tech-code task-runner sub-agent.

Usage:
    python3 resolve_task_context.py \
        --task-id t1 \
        --cycle-dir /abs/path/.cache/cursor/lulu-dev-workflow/<cycle_id> \
        --work-order-index r1 \
        --code-index s1 \
        --project-root /abs/path/to/project

Outputs a JSON object to stdout with all paths and config values the
task-runner sub-agent needs. No further file reads or path derivation
is required by the sub-agent.
"""

import argparse
import json
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resolve task-runner context paths.")
    p.add_argument("--task-id", required=True, help="Task ID, e.g. t1")
    p.add_argument("--cycle-dir", required=True, help="Absolute path to the cycle cache directory.")
    p.add_argument("--work-order-index", required=True, help="Work-order session index, e.g. r1")
    p.add_argument("--code-index", required=True, help="Code session index, e.g. s1")
    p.add_argument("--project-root", required=True, help="Absolute path to the project root.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    cycle_dir = Path(args.cycle_dir).resolve()
    project_root = Path(args.project_root).resolve()
    task_id = args.task_id
    wo_index = args.work_order_index
    code_index = args.code_index

    work_order_task_path = cycle_dir / "tech" / "work-order" / wo_index / "tasks" / task_id / "task.md"
    task_output_dir = cycle_dir / "tech" / "code" / code_index / "tasks" / task_id
    code_task_list_path = cycle_dir / "tech" / "code" / code_index / "code-task-list.md"
    workspace_json_path = cycle_dir / "tech" / "code" / code_index / "workspace.json"

    if not workspace_json_path.exists():
        print(f"Error: workspace.json not found: {workspace_json_path}", file=sys.stderr)
        return 1

    workspace = json.loads(workspace_json_path.read_text(encoding="utf-8"))
    worktree_path_raw = workspace.get("worktree_path", "")
    if not worktree_path_raw:
        print("Error: workspace.json missing 'worktree_path'", file=sys.stderr)
        return 1

    worktree_path = Path(worktree_path_raw)
    if not worktree_path.is_absolute():
        worktree_path = (project_root / worktree_path).resolve()

    config_path = project_root / "skill-config" / "lulu-dev-workflow" / "workflow-config.json"
    if not config_path.exists():
        print(f"Error: workflow-config.json not found: {config_path}", file=sys.stderr)
        return 1

    config = json.loads(config_path.read_text(encoding="utf-8"))
    code_cfg = config.get("tech-code", {})
    git_cfg = code_cfg.get("git", {})

    result = {
        "task_id": task_id,
        "work_order_task_path": str(work_order_task_path),
        "task_output_dir": str(task_output_dir),
        "code_task_list_path": str(code_task_list_path),
        "worktree_abs_path": str(worktree_path),
        "commit_message_template": git_cfg.get("commit_message_template", ""),
        "test_command": code_cfg.get("test_command", ""),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
