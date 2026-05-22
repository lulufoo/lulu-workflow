#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from workflow_common import (
    CACHE_DIR,
    WHITELIST_PATH,
    all_tasks_done,
    get_done_task_ids,
    get_task_depends,
    normalize_tool_path,
    parse_frontmatter_fields,
    parse_frontmatter_state,
    read_md_field,
    read_md_state,
    read_json,
    task_list_path,
)

# Matches: .cache/<platform>/lulu-dev-workflow/code/<conv_id>/s{N}/workflow-state.md
_PLATFORM = CACHE_DIR.parts[1]
_CACHE_PARTS = (".cache", _PLATFORM, "lulu-dev-workflow", "code")

# Phases that are valid as current_phase values
_KNOWN_PHASES = {
    "WriteTests", "VerifyRed", "WriteImpl", "VerifyGreen", "Refactor", "Done",
}

# Session-level states
_KNOWN_STATES = {"Executing", "Completed"}


def allow() -> Dict[str, str]:
    return {"permission": "allow"}


def deny(user_message: str, agent_message: str = "") -> Dict[str, str]:
    payload = {"permission": "deny", "user_message": user_message}
    if agent_message:
        payload["agent_message"] = agent_message
    return payload


def load_event() -> Dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def extract_tool_name(event: Dict[str, Any]) -> str:
    return str(event.get("tool_name") or event.get("tool") or event.get("name") or "")


def extract_path_and_contents(event: Dict[str, Any], project_root: Path) -> Tuple[str, str]:
    tool_input = event.get("tool_input") or event.get("arguments") or {}
    raw_path = (
        tool_input.get("path")
        or tool_input.get("target_file")
        or tool_input.get("file_path")
        or ""
    )
    normalized = normalize_tool_path(str(raw_path), project_root) if raw_path else ""
    contents = tool_input.get("content") or tool_input.get("contents")
    return normalized, (contents if isinstance(contents, str) else "")


def match_workflow_state_path(path: str) -> Optional[Tuple[str, str]]:
    """Return (conv_id, session_round_str) if path is s{N}/workflow-state.md under tdd cache."""
    parts = Path(path).parts
    if (
        len(parts) == 7
        and parts[:4] == _CACHE_PARTS
        and re.match(r"^s\d+$", parts[5])
        and parts[6] == "workflow-state.md"
    ):
        return parts[4], parts[5]  # conv_id, s{N}
    return None


def main() -> int:
    project_root = Path.cwd()

    try:
        event = load_event()
    except json.JSONDecodeError as exc:
        print(json.dumps(deny(f"Invalid hook input JSON: {exc}")))
        return 0

    tool_name = extract_tool_name(event)
    if tool_name not in {"Write", "Edit"}:
        print(json.dumps(allow()))
        return 0

    path, contents = extract_path_and_contents(event, project_root)
    match = match_workflow_state_path(path)

    if match is None:
        print(json.dumps(allow()))
        return 0

    conv_id, session_round_str = match
    s_dir = project_root / CACHE_DIR / "code" / conv_id / session_round_str

    # -----------------------------------------------------------------------
    # Check 1: Deny Edit (only Write allowed)
    # -----------------------------------------------------------------------
    if tool_name == "Edit" and not contents:
        print(json.dumps(deny(
            "Workflow state file must be written in full, not as a partial Edit.",
            "Use a full Write operation when updating workflow-state.md.",
        )))
        return 0

    # -----------------------------------------------------------------------
    # Parse incoming workflow-state.md
    # -----------------------------------------------------------------------
    to_state = parse_frontmatter_state(contents)
    if not to_state:
        print(json.dumps(deny(
            "workflow-state.md must contain a YAML frontmatter block with a 'current_state' field.",
            "Ensure the file starts with '---' and includes 'current_state: <State>'.",
        )))
        return 0

    incoming_fields = parse_frontmatter_fields(contents)
    to_phase = incoming_fields.get("current_phase", "").strip()
    to_task = incoming_fields.get("current_task", "").strip()

    # Read current state from disk
    state_file = s_dir / "workflow-state.md"
    current_state = read_md_state(state_file, default="Executing")
    current_phase = read_md_field(state_file, "current_phase", default="")
    current_task = read_md_field(state_file, "current_task", default="")

    # -----------------------------------------------------------------------
    # Load whitelist
    # -----------------------------------------------------------------------
    whitelist = read_json(WHITELIST_PATH, default={"allowed_transitions": []})
    allowed_edges = {
        (edge.get("from"), edge.get("to"))
        for edge in whitelist.get("allowed_transitions", [])
    }

    tl_file = s_dir / "code-task-list.md"

    # -----------------------------------------------------------------------
    # Check 2: Session-level state transition (Executing → Completed)
    # -----------------------------------------------------------------------
    if to_state != current_state:
        if (current_state, to_state) not in allowed_edges:
            print(json.dumps(deny(
                f"非法 Session 状态迁移：'{current_state}' → '{to_state}'。",
                "Requested session transition is not in the workflow whitelist.",
            )))
            return 0

        if to_state == "Completed":
            if not all_tasks_done(tl_file):
                print(json.dumps(deny(
                    "code-task-list.md 中仍有未完成的任务（checkbox 未全部勾选）。请完成所有任务后再标记 Completed。",
                    "All tasks in code-task-list.md must be checked [x] before transitioning to Completed.",
                )))
                return 0

        print(json.dumps(allow()))
        return 0

    # -----------------------------------------------------------------------
    # Check 3: Phase transition validation (same session state = Executing)
    # -----------------------------------------------------------------------
    if to_phase and to_phase != current_phase:
        # Validate phase is known
        if to_phase not in _KNOWN_PHASES and to_phase != "":
            print(json.dumps(deny(
                f"未知的 Phase 值：'{to_phase}'。合法值：{', '.join(sorted(_KNOWN_PHASES))}",
                f"Unknown phase value: '{to_phase}'.",
            )))
            return 0

        if (current_phase, to_phase) not in allowed_edges:
            print(json.dumps(deny(
                f"非法 Phase 转换：'{current_phase}' → '{to_phase}'。请按顺序执行各 Phase。",
                f"Phase transition '{current_phase}' → '{to_phase}' is not allowed.",
            )))
            return 0

        # Check 4: Dependency pre-condition when starting a new task (entering WriteTests)
        if to_phase == "WriteTests" and to_task and to_task != current_task:
            depends = get_task_depends(tl_file, to_task)
            if depends:
                done_ids = set(get_done_task_ids(tl_file))
                unfinished = [d for d in depends if d not in done_ids]
                if unfinished:
                    print(json.dumps(deny(
                        f"任务 {to_task} 的前置依赖 [{', '.join(unfinished)}] 尚未完成。"
                        f"请按依赖顺序先完成前置任务。",
                        f"Task {to_task} has unfinished dependencies: {unfinished}.",
                    )))
                    return 0

        # Check 5: VerifyRed → WriteImpl requires red-run.md to exist
        if to_phase == "WriteImpl" and current_phase == "VerifyRed":
            effective_task = to_task or current_task
            if effective_task:
                red_run_file = s_dir / "tasks" / effective_task / "red-run.md"
                if not red_run_file.exists():
                    print(json.dumps(deny(
                        f"red-run.md 不存在（tasks/{effective_task}/red-run.md）。"
                        f"请先运行测试并将输出写入该文件，确认测试全部 FAIL 后再写实现代码。",
                        f"tasks/{effective_task}/red-run.md must exist before transitioning to WriteImpl.",
                    )))
                    return 0

    print(json.dumps(allow()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
