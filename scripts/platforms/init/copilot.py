"""Register lulu-dev-workflow preToolUse hook in Copilot hooks.json."""

from __future__ import annotations

import json
from pathlib import Path

from platforms.paths import hook_guard_command, hooks_config_path


def register_copilot_hook(project_root: Path) -> None:
    hooks_path = project_root / hooks_config_path("copilot")
    payload: dict = {"version": 1, "hooks": {}}
    if hooks_path.exists():
        with hooks_path.open(encoding="utf-8") as f:
            payload = json.load(f)
    hooks = payload.setdefault("hooks", {})
    command = hook_guard_command("copilot")
    pre_tool_use = hooks.get("PreToolUse", [])
    pre_tool_use = [
        e for e in pre_tool_use
        if "lulu-dev-workflow" not in e.get("command", "")
    ]
    pre_tool_use.append({"type": "command", "command": command, "timeout": 5})
    hooks["PreToolUse"] = pre_tool_use
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    with hooks_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
