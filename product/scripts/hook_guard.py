#!/usr/bin/env python3
"""Format guard: deny writes of non-.md files to the workflow cache."""

import json
import sys
from pathlib import Path
from typing import Dict

from workflow_common import CACHE_DIR, normalize_tool_path


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

    path = Path(normalize_tool_path(str(raw_path), project_root))
    workflow_cache = project_root / CACHE_DIR

    try:
        path.relative_to(workflow_cache)
    except ValueError:
        print(json.dumps(allow()))
        return 0

    if path.suffix.lower() != ".md":
        print(json.dumps(deny(
            f"workflow cache 只允许写入 .md 文件（收到: {path.name}）。",
            f"Only .md files are allowed in the workflow cache. Got: {path.name}",
        )))
        return 0

    print(json.dumps(allow()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
