#!/usr/bin/env python3
"""Unified preToolUse entry point. Routes to the active stage's hook_guard."""

import argparse
import importlib.util
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from active_context import get_entry

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_PLATFORMS_DIR = Path(__file__).resolve().parent / "platforms"
_WRITE_TOOL_NAMES = frozenset({"Write", "Edit"})
_KNOWN_STAGES = frozenset({
    "diagnostic",
    "product-diagnostic", "tech-diagnostic",
    "product-plan", "tech-plan",
    "tech-work-order", "tech-code",
})


def _load_platform(platform: str):
    path = _PLATFORMS_DIR / f"{platform}.py"
    spec = importlib.util.spec_from_file_location(f"_platform_{platform}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_stage_module(stage: str):
    path = _SKILL_ROOT / stage / "scripts" / "hook_guard.py"
    stage_scripts = str(path.parent)
    sys.path.insert(0, stage_scripts)
    sys.modules.pop("workflow_common", None)
    try:
        spec = importlib.util.spec_from_file_location(f"_{stage}_hook_guard", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        try:
            sys.path.remove(stage_scripts)
        except ValueError:
            pass
        sys.modules.pop("workflow_common", None)
        sys.modules.pop(f"_{stage}_hook_guard", None)


# Any .py under the lulu-dev-workflow skill root (any subdir).
_WORKFLOW_PY_PATH = re.compile(
    r"lulu-dev-workflow[/\\][^\s;|&\"']+\.py\b"
)


def _should_inject_conversation_id(command: str) -> bool:
    if "--conversation-id" in command:
        return False
    if not re.search(r"\bpython3?\b", command):
        return False
    return bool(_WORKFLOW_PY_PATH.search(command))


def _read_active_stage(platform: str, conversation_id: str) -> Optional[str]:
    if not conversation_id:
        return None
    entry = get_entry(Path.cwd(), platform, conversation_id)
    if entry is None:
        return None
    stage = entry.get("stage")
    return stage if stage in _KNOWN_STAGES else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--platform", default="cursor",
        choices=["cursor", "copilot", "claude"],
        help="Platform invoking this hook.",
    )
    args, _ = parser.parse_known_args()

    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"permission": "allow"}))
        return 0

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print(json.dumps({"permission": "allow"}))
        return 0

    # Propagate platform to stage workflow_common.py via env var
    os.environ["LULU_PLATFORM"] = args.platform

    # Normalize payload to Cursor format
    platform_mod = _load_platform(args.platform)
    normalized = platform_mod.normalize(payload)

    # Early-return allow for non-write tools
    tool_name = str(normalized.get("tool_name") or "")

    # Inject conversation_id into lulu-dev-workflow shell commands
    if tool_name == "Shell":
        try:
            tool_input = normalized.get("tool_input") or {}
            command = tool_input.get("command", "")
            conv_id = (normalized.get("conversation_id") or "").strip()
            if conv_id and _should_inject_conversation_id(command):
                new_cmd = f"{command} --conversation-id {conv_id}"
                print(json.dumps({
                    "permission": "allow",
                    "updated_input": {"command": new_cmd},
                }))
                return 0
        except Exception:
            pass
        print(json.dumps({"permission": "allow"}))
        return 0

    if tool_name not in _WRITE_TOOL_NAMES:
        print(json.dumps({"permission": "allow"}))
        return 0

    # Determine active stage
    conv_id = (normalized.get("conversation_id") or "").strip()
    stage = _read_active_stage(args.platform, conv_id)
    if stage is None:
        print(json.dumps({"permission": "allow"}))
        return 0

    stage_path = _SKILL_ROOT / stage / "scripts" / "hook_guard.py"
    if not stage_path.exists():
        print(json.dumps({"permission": "allow"}))
        return 0

    normalized_raw = json.dumps(normalized)
    sys.stdin = io.StringIO(normalized_raw)
    captured = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        mod = _load_stage_module(stage)
        mod.main()
    except SystemExit:
        pass
    finally:
        sys.stdout = old_stdout

    output = captured.getvalue().strip()
    if output:
        try:
            result = json.loads(output)
            print(json.dumps(result))
            return 0
        except json.JSONDecodeError:
            pass

    print(json.dumps({"permission": "allow"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
