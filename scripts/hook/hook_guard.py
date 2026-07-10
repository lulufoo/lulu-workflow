#!/usr/bin/env python3
"""preToolUse entry point for lulu-dev-workflow hooks."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

_HOOK_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _HOOK_DIR.parent
for path in (_HOOK_DIR, _SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from active_context_schema import get_entry  # noqa: E402
from hook_config_schema import resolve_rw_guard  # noqa: E402
from platforms.hook.loader import load_hook_adapter  # noqa: E402
from platforms.paths import cache_dir as platform_cache_dir  # noqa: E402
from rw_guard import (  # noqa: E402
    allowed_dirs_for_tool,
    extract_tool_path,
    is_rw_tool,
    is_write_tool,
    normalize_tool_path,
    path_under_any_allowed,
    resolve_allowed_dirs,
)
from transition_table import allowed_stages  # noqa: E402
from workflow_hook_common import deny_rw_boundary  # noqa: E402
from workflow_sessions import current_effective_delivered  # noqa: E402

_WORKFLOW_PY_PATH = re.compile(
    r"lulu-dev-workflow[/\\][^\s;|&\"']+\.py\b"
)

_CONV_ID_INJECT_SCRIPT_SUFFIXES = (
    "/compose/scripts/core/start.py",
    "/compose/scripts/inductive/inductive_gate_control.py",
    "/compose/scripts/inductive/inductive_g3_grounding_control.py",
    "/compose/scripts/inductive/inductive_g2_control.py",
    "/compose/scripts/inductive/inductive_g4_control.py",
    "/lulu-code/scripts/tc_start.py",
    "/lulu-code/scripts/tc_task_control.py",
    "/decision/scripts/dec_start.py",
    "/lulu-tasks/scripts/tt_start.py",
)

# Inductive grounding controls: always bind to the hook conversation id (override agent typos).
_INDUCTIVE_CONV_OVERRIDE_SUFFIXES = (
    "/compose/scripts/inductive/inductive_gate_control.py",
    "/compose/scripts/inductive/inductive_g3_grounding_control.py",
    "/compose/scripts/inductive/inductive_g2_control.py",
    "/compose/scripts/inductive/inductive_g4_control.py",
)

_CONV_ID_ARG = re.compile(
    r'--conversation-id(?:=(\S+)|\s+"([^"]*)"|\'([^\']*)\'|\s+(\S+))'
)


def _emit_response(
    platform_mod,
    response: dict,
    *,
    tool_name: str = "",
    tool_input: object = None,
) -> None:
    formatter = getattr(platform_mod, "format_response", None)
    if callable(formatter):
        payload = formatter(
            response,
            tool_name=tool_name,
            tool_input=tool_input if isinstance(tool_input, dict) else {},
        )
    else:
        payload = response
    print(json.dumps(payload))


def _should_inject_conversation_id(command: str) -> bool:
    if "--conversation-id" in command:
        return False
    if not re.search(r"\bpython3?\b", command):
        return False
    if not _WORKFLOW_PY_PATH.search(command):
        return False
    return any(suffix in command for suffix in _CONV_ID_INJECT_SCRIPT_SUFFIXES)


def _should_override_conversation_id(command: str) -> bool:
    if not re.search(r"\bpython3?\b", command):
        return False
    if not _WORKFLOW_PY_PATH.search(command):
        return False
    return any(suffix in command for suffix in _INDUCTIVE_CONV_OVERRIDE_SUFFIXES)


def _apply_conversation_id(command: str, conv_id: str) -> Optional[str]:
    """Append or replace --conversation-id for workflow shell commands.

    Operates per newline-separated statement, not on the whole command blob:
    a multi-line Shell call may mix an injectable script (e.g.
    inductive_gate_control.py) with a non-injectable one (e.g.
    inductive_g3_section_control.py, which has no --conversation-id flag and
    needs none — see inductive_subagent_guard). Matching on the full string
    would append the flag once at the very end, landing on whichever
    statement happens to be last (wrong target, and on a trailing empty line
    when the command ends with "\\n" it becomes a bare, invalid statement).
    """
    if not conv_id:
        return None
    lines = command.split("\n")
    changed = False
    for idx, line in enumerate(lines):
        if not line.strip():
            continue
        if _should_override_conversation_id(line):
            if _CONV_ID_ARG.search(line):
                new_line = _CONV_ID_ARG.sub(f"--conversation-id {conv_id}", line, count=1)
            else:
                new_line = f"{line} --conversation-id {conv_id}"
        elif _should_inject_conversation_id(line):
            new_line = f"{line} --conversation-id {conv_id}"
        else:
            continue
        if new_line != line:
            lines[idx] = new_line
            changed = True
    if not changed:
        return None
    return "\n".join(lines)


def _workflow_cache_dir(platform: str) -> Path:
    return Path.cwd() / platform_cache_dir(platform)


def _read_active_entry(platform: str, conversation_id: str):
    if not conversation_id:
        return None
    return get_entry(Path.cwd(), platform, conversation_id)


def _read_active_stage(platform: str, conversation_id: str) -> Optional[str]:
    entry = _read_active_entry(platform, conversation_id)
    if entry is None:
        return None
    stage = entry.get("stage")
    cycle_type = entry.get("cycle_type", "feature")
    if cycle_type not in ("feature", "topic"):
        cycle_type = "feature"
    return stage if stage in allowed_stages(cycle_type) else None


def _tool_kind(tool_name: str) -> str:
    if tool_name == "Read":
        return "Read"
    return "Write"


def _evaluate_rw_guard(
    *,
    platform: str,
    stage: str,
    tool_name: str,
    tool_input: object,
    entry,
) -> Optional[dict]:
    project_root = Path.cwd()
    guard = resolve_rw_guard(project_root, stage, platform=platform)
    if not guard.get("enable", True):
        return None

    if is_write_tool(tool_name):
        if entry and current_effective_delivered(
            entry["cycle_id"],
            stage,
            _workflow_cache_dir(platform),
        ):
            return None

    dir_templates = allowed_dirs_for_tool(
        tool_name,
        read_dirs=guard.get("readDirs", ["."]),
        write_dirs=guard.get("writeDirs", [platform_cache_dir(platform).as_posix()]),
    )
    raw_path = extract_tool_path(tool_name, tool_input)
    if not raw_path:
        return None

    target = normalize_tool_path(raw_path, project_root)
    allowed_roots = resolve_allowed_dirs(project_root, dir_templates)
    if path_under_any_allowed(target, allowed_roots):
        return None

    return deny_rw_boundary(
        stage=stage,
        tool_kind=_tool_kind(tool_name),
        allowed_dirs=allowed_roots,
        target_path=target,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--platform",
        default="cursor",
        choices=["cursor", "copilot", "claude"],
        help="Platform invoking this hook.",
    )
    args, _ = parser.parse_known_args()

    raw = sys.stdin.read().strip()
    if not raw:
        _emit_response(load_hook_adapter(args.platform), {"permission": "allow"})
        return 0

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        _emit_response(load_hook_adapter(args.platform), {"permission": "allow"})
        return 0

    prev_platform = os.environ.get("LULU_PLATFORM")
    os.environ["LULU_PLATFORM"] = args.platform
    try:
        platform_mod = load_hook_adapter(args.platform)
        normalized = platform_mod.normalize(payload)

        tool_name = str(normalized.get("tool_name") or "")
        tool_input = normalized.get("tool_input") or {}

        if tool_name == "Shell":
            try:
                command = tool_input.get("command", "")
                conv_id = (normalized.get("conversation_id") or "").strip()
                new_cmd = _apply_conversation_id(command, conv_id)
                if new_cmd:
                    _emit_response(
                        platform_mod,
                        {
                            "permission": "allow",
                            "updated_input": {"command": new_cmd},
                        },
                        tool_name=tool_name,
                        tool_input=tool_input,
                    )
                    return 0
            except Exception:
                pass
            _emit_response(platform_mod, {"permission": "allow"})
            return 0

        if not is_rw_tool(tool_name):
            _emit_response(platform_mod, {"permission": "allow"})
            return 0

        conv_id = (normalized.get("conversation_id") or "").strip()
        stage = _read_active_stage(args.platform, conv_id)
        if stage is None:
            _emit_response(platform_mod, {"permission": "allow"})
            return 0

        entry = _read_active_entry(args.platform, conv_id)
        deny = _evaluate_rw_guard(
            platform=args.platform,
            stage=stage,
            tool_name=tool_name,
            tool_input=tool_input,
            entry=entry,
        )
        if deny is not None:
            _emit_response(platform_mod, deny, tool_name=tool_name, tool_input=tool_input)
            return 0

        _emit_response(platform_mod, {"permission": "allow"})
        return 0
    finally:
        if prev_platform is None:
            os.environ.pop("LULU_PLATFORM", None)
        else:
            os.environ["LULU_PLATFORM"] = prev_platform


if __name__ == "__main__":
    sys.exit(main())
