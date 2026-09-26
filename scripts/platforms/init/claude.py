"""Register lulu-dev-workflow preToolUse hook in Claude settings.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from platforms.init.common import strip_lulu_hook_entries
from platforms.paths import (
    CLAUDE_PRE_TOOL_USE_MATCHER,
    hook_guard_command,
    hooks_config_path,
)


def _upsert_claude_pre_tool_use(entries: list[Any], hook_command: str) -> list[Any]:
    entries = strip_lulu_hook_entries(entries)
    new_hook = {"type": "command", "command": hook_command, "timeout": 5}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if entry.get("matcher") != CLAUDE_PRE_TOOL_USE_MATCHER:
            continue
        hooks = [
            item for item in (entry.get("hooks") or [])
            if item.get("command") != hook_command
        ]
        hooks.append(new_hook)
        entry["hooks"] = hooks
        return entries
    entries.append({"matcher": CLAUDE_PRE_TOOL_USE_MATCHER, "hooks": [new_hook]})
    return entries


def register_claude_hook(project_root: Path) -> None:
    settings_path = project_root / hooks_config_path("claude")
    payload: dict = {}
    if settings_path.exists():
        with settings_path.open(encoding="utf-8") as f:
            payload = json.load(f)
    hooks = payload.setdefault("hooks", {})
    pre_tool_use = hooks.get("PreToolUse", [])
    if not isinstance(pre_tool_use, list):
        pre_tool_use = []
    command = hook_guard_command("claude")
    hooks["PreToolUse"] = _upsert_claude_pre_tool_use(pre_tool_use, command)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with settings_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
