#!/usr/bin/env python3
"""Resolve all file paths needed by a tech-code task-runner sub-agent.

Usage:
    python3 resolve_task_context.py \
        --task-id t1 \
        --cycle-dir /abs/path/.cache/cursor/lulu-dev-workflow/<cycle_id> \
        --project-root /abs/path/to/project

Reads work-order and code session indices from their respective
session-state.md files. Outputs a JSON object to stdout with all paths
and config values the task-runner sub-agent needs.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from workspace_schema import load_workspace  # noqa: E402


def _read_active_session(session_state_path: Path) -> str:
    for line in session_state_path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^active_session:\s*(\S+)", line)
        if m:
            return m.group(1)
    raise ValueError(f"active_session not found in {session_state_path}")


def _read_work_order_round(session_state_path: Path) -> str:
    """Read work-order round index from session-state.md.

    Prefer active_doc (current contract), fallback to active_session
    for backward compatibility.
    """
    for line in session_state_path.read_text(encoding="utf-8").splitlines():
        m_doc = re.match(r"^active_doc:\s*(\S+)", line)
        if m_doc:
            return m_doc.group(1)
    return _read_active_session(session_state_path)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resolve task-runner context paths.")
    p.add_argument("--task-id", required=True, help="Task ID, e.g. t1")
    p.add_argument("--cycle-dir", required=True, help="Absolute path to the cycle cache directory.")
    p.add_argument("--project-root", required=True, help="Absolute path to the project root.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    cycle_dir = Path(args.cycle_dir).resolve()
    project_root = Path(args.project_root).resolve()
    task_id = args.task_id

    wo_session_state = cycle_dir / "tech" / "work-order" / "session-state.md"
    code_session_state = cycle_dir / "tech" / "code" / "session-state.md"

    for path in (wo_session_state, code_session_state):
        if not path.exists():
            print(f"Error: session-state.md not found: {path}", file=sys.stderr)
            return 1

    wo_index = f"r{_read_work_order_round(wo_session_state)}"
    code_index = f"s{_read_active_session(code_session_state)}"

    work_order_task_path = cycle_dir / "tech" / "work-order" / wo_index / "tasks" / task_id / "task.md"
    task_output_dir = cycle_dir / "tech" / "code" / code_index / "tasks" / task_id
    code_task_list_path = cycle_dir / "tech" / "code" / code_index / "code-task-list.md"
    workspace_json_path = cycle_dir / "tech" / "code" / code_index / "workspace.json"

    if not workspace_json_path.exists():
        print(f"Error: workspace.json not found: {workspace_json_path}", file=sys.stderr)
        return 1

    try:
        workspace = load_workspace(workspace_json_path)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    worktree_path = Path(workspace["worktree_path"])

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
