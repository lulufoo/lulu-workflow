#!/usr/bin/env python3

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from workflow_common import (
    WHITELIST_PATH,
    WORKFLOW_DIR,
    approval_path,
    normalize_tool_path,
    read_json,
)

# Matches: .cursor/lulu-dev-workflow/product/<conv_id>/state.json
_STATE_PARTS = (".cursor", "lulu-dev-workflow", "product")


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
    contents = tool_input.get("contents")
    return normalized, (contents if isinstance(contents, str) else "")


def match_state_conv_id(path: str) -> Optional[str]:
    """Return conversation_id if path is .cursor/lulu-dev-workflow/product/<conv_id>/state.json."""
    parts = Path(path).parts
    if (
        len(parts) == 5
        and parts[:3] == _STATE_PARTS
        and parts[4] == "state.json"
    ):
        return parts[3]
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
    conv_id = match_state_conv_id(path)

    if conv_id is None:
        print(json.dumps(allow()))
        return 0

    if tool_name == "Edit" and not contents:
        print(json.dumps(deny(
            "State file must be written in full, not as a partial Edit.",
            "Use a full Write operation when updating state.json.",
        )))
        return 0

    try:
        proposed = json.loads(contents)
    except json.JSONDecodeError as exc:
        print(json.dumps(deny(f"state.json content is not valid JSON: {exc}")))
        return 0

    to_state = proposed.get("current_state")
    if not to_state:
        print(json.dumps(deny("state.json must contain a 'current_state' field.")))
        return 0

    state_file = project_root / WORKFLOW_DIR / "product" / conv_id / "state.json"
    current = read_json(state_file, default={"current_state": "Drafting"})
    current_state = current.get("current_state", "Drafting")

    if to_state == current_state:
        print(json.dumps(allow()))
        return 0

    whitelist = read_json(WHITELIST_PATH, default={"allowed_transitions": []})
    allowed_edges = {
        (edge.get("from"), edge.get("to"))
        for edge in whitelist.get("allowed_transitions", [])
    }

    if (current_state, to_state) not in allowed_edges:
        print(json.dumps(deny(
            f"Illegal transition: '{current_state}' \u2192 '{to_state}'.",
            "Requested transition is not in the workflow whitelist.",
        )))
        return 0

    if to_state == "Delivered":
        appr_file = project_root / approval_path(conv_id)
        appr = read_json(appr_file, default={"approved": False})
        if not appr.get("approved", False):
            print(json.dumps(deny(
                "ReadyForDelivery \u2192 Delivered requires delivery approval first.",
                "Write delivery-approval.json with approved=true in the same session directory.",
            )))
            return 0

    print(json.dumps(allow()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
