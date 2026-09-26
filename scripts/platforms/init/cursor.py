"""Register lulu-workflow preToolUse + beforeSubmitPrompt hooks in Cursor hooks.json."""

from __future__ import annotations

import json
from pathlib import Path

from platforms.paths import (
    CURSOR_PRE_TOOL_USE_MATCHER,
    hook_guard_command,
    hook_prompt_command,
    hooks_config_path,
)


def register_cursor_hook(project_root: Path) -> None:
    hooks_path = project_root / hooks_config_path("cursor")
    payload: dict = {"version": 1, "hooks": {}}
    if hooks_path.exists():
        with hooks_path.open(encoding="utf-8") as f:
            payload = json.load(f)
    hooks = payload.setdefault("hooks", {})

    pre_tool_use = [
        e
        for e in hooks.get("preToolUse", [])
        if "lulu-workflow" not in e.get("command", "")
    ]
    pre_tool_use.append({
        "matcher": CURSOR_PRE_TOOL_USE_MATCHER,
        "command": hook_guard_command("cursor"),
        "timeout": 5,
        "failClosed": True,
    })
    hooks["preToolUse"] = pre_tool_use

    existing_prompt = hooks.get("beforeSubmitPrompt", [])
    if not isinstance(existing_prompt, list):
        existing_prompt = []
    before_submit = [
        e
        for e in existing_prompt
        if "hook_prompt.py" not in e.get("command", "")
    ]
    before_submit.append({
        "command": hook_prompt_command("cursor"),
        "timeout": 5,
    })
    hooks["beforeSubmitPrompt"] = before_submit

    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    with hooks_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
