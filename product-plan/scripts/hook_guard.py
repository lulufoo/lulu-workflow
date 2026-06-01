#!/usr/bin/env python3
"""Stage guard: only allow writes inside the workflow cache."""

import json
import sys
from pathlib import Path
from typing import Dict

from workflow_common import CACHE_DIR, STAGE, normalize_tool_path


def allow() -> Dict[str, str]:
    return {"permission": "allow"}


def deny(user_message: str, agent_message: str = "") -> Dict[str, str]:
    payload = {"permission": "deny", "user_message": user_message}
    if agent_message:
        payload["agent_message"] = agent_message
    return payload


def main() -> int:
    project_root = Path.cwd()

    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps(allow()))
        return 0

    try:
        event = json.loads(raw)
    except json.JSONDecodeError:
        print(json.dumps(allow()))
        return 0

    tool_name = str(event.get("tool_name") or event.get("tool") or "")
    if tool_name not in {"Write", "Edit"}:
        print(json.dumps(allow()))
        return 0

    tool_input = event.get("tool_input") or event.get("arguments") or {}
    raw_path = (
        tool_input.get("path")
        or tool_input.get("target_file")
        or tool_input.get("file_path")
        or ""
    )
    if not raw_path:
        print(json.dumps(allow()))
        return 0

    rel = normalize_tool_path(str(raw_path), project_root)
    abs_path = (project_root / rel).resolve()
    workflow_cache = (project_root / CACHE_DIR).resolve()

    try:
        abs_path.relative_to(workflow_cache)
    except ValueError:
        print(json.dumps(deny(
            f"{STAGE} 阶段只允许写入 workflow cache 目录（{CACHE_DIR}）。",
            f"Stage '{STAGE}' may only write inside the workflow cache. Got: {abs_path}",
        )))
        return 0

    print(json.dumps(allow()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
