#!/usr/bin/env python3
"""Top-level orchestrator: runs each sub-workflow init.py in sequence.

Hook paths and config defaults are owned by each sub-workflow's own
workflow_common.py / init.py — this script only dispatches to them.
"""

import argparse
import json
import subprocess
import sys
import os
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = SKILL_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from subagent_config import ensure_platform_config  # noqa: E402
SUB_WORKFLOWS = ["product-plan", "tech-plan", "tech-work-order", "tech-code"]

_CURSOR_HOOK_COMMAND = (
    "python3 ~/.cursor/skills/lulu-dev-workflow/scripts/hook_guard.py"
)
_COPILOT_HOOK_COMMAND = (
    "python3 ~/.copilot/skills/lulu-dev-workflow/scripts/hook_guard.py"
    " --platform copilot"
)


def register_cursor_hook(project_root: Path) -> None:
    hooks_path = project_root / ".cursor" / "hooks.json"
    payload: dict = {"version": 1, "hooks": {}}
    if hooks_path.exists():
        with hooks_path.open(encoding="utf-8") as f:
            payload = json.load(f)
    hooks = payload.setdefault("hooks", {})
    pre_tool_use = hooks.get("preToolUse", [])
    pre_tool_use = [
        e for e in pre_tool_use
        if "lulu-dev-workflow" not in e.get("command", "")
    ]
    pre_tool_use.append({
        "matcher": "Write|Edit|Shell",
        "command": _CURSOR_HOOK_COMMAND,
        "timeout": 5,
        "failClosed": True,
    })
    hooks["preToolUse"] = pre_tool_use
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    with hooks_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def register_copilot_hook(project_root: Path) -> None:
    hooks_path = project_root / ".github" / "hooks" / "hooks.json"
    payload: dict = {"version": 1, "hooks": {}}
    if hooks_path.exists():
        with hooks_path.open(encoding="utf-8") as f:
            payload = json.load(f)
    hooks = payload.setdefault("hooks", {})
    # Copilot uses PascalCase hook names
    pre_tool_use = hooks.get("PreToolUse", [])
    pre_tool_use = [
        e for e in pre_tool_use
        if "lulu-dev-workflow" not in e.get("command", "")
    ]
    pre_tool_use.append({"type": "command", "command": _COPILOT_HOOK_COMMAND, "timeout": 5})
    hooks["PreToolUse"] = pre_tool_use
    # Ensure Stop hook is preserved (do not overwrite unrelated entries)
    hooks_path.parent.mkdir(parents=True, exist_ok=True)
    with hooks_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")


def ensure_copilot_platform_config(project_root: Path) -> None:
    """Create or migrate .github/lulu-dev-workflow/config.json."""
    ensure_platform_config(project_root, platform="copilot")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Initialize lulu-dev-workflow in a project (all sub-workflows)."
    )
    parser.add_argument("--project-root", required=True, help="Project root directory.")
    parser.add_argument(
        "--platform", default="cursor",
        choices=["cursor", "copilot"],
        help="Target platform (cursor or copilot).",
    )
    args, _ = parser.parse_known_args()
    project_root = Path(args.project_root).resolve()

    for sub in SUB_WORKFLOWS:
        init_py = SKILL_ROOT / sub / "scripts" / "init.py"
        if not init_py.exists():
            print(f"[lulu-dev-workflow init] WARNING: {init_py} not found, skipping.")
            continue
        print(f"\n[lulu-dev-workflow init] Running {sub} init...")
        result = subprocess.run(
            [sys.executable, str(init_py), "--project-root", args.project_root],
            env={**os.environ, "LULU_PLATFORM": args.platform},
            check=False,
        )
        if result.returncode != 0:
            print(f"[lulu-dev-workflow init] ERROR: {sub} init failed (exit {result.returncode}).")
            return result.returncode

    if args.platform == "copilot":
        ensure_copilot_platform_config(project_root)
        register_copilot_hook(project_root)
        print(f"\n[lulu-dev-workflow init] Copilot hook registered: {_COPILOT_HOOK_COMMAND}")
    else:
        register_cursor_hook(project_root)
        print(f"\n[lulu-dev-workflow init] Cursor hook registered: {_CURSOR_HOOK_COMMAND}")

    print("\n[lulu-dev-workflow init] All sub-workflows initialized successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
