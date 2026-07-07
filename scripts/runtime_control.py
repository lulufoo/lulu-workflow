#!/usr/bin/env python3
"""Runtime bootstrap control for lulu-dev-workflow.

Subcommands:
    resolve-platform-context   Emit platform context JSON for session bootstrap
    resolve-session-context    Emit session context JSON from active-context + cycles
    set-execution-mode         Update execution_mode via cycle_control (facade)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from active_context_schema import get_entry, resolve_conversation_id
from cycle_control import cmd_set_execution_mode as cycle_cmd_set_execution_mode
from cycle_schema import build_cycle_info, resolve_cache_dir
from platform_schema import PlatformDetectionError, detect_platform, resolve_platform_context

_CMD_RESOLVE_PLATFORM_CONTEXT = "resolve-platform-context"
_CMD_RESOLVE_SESSION_CONTEXT = "resolve-session-context"
_CMD_SET_EXECUTION_MODE = "set-execution-mode"


def _empty_session_payload(conversation_id: str = "") -> dict[str, str]:
    return {
        "conversation_id": conversation_id,
        "cycle_id": "",
        "cycle_type": "",
        "stage": "",
        "execution_mode": "",
    }


def cmd_resolve_platform_context(args: argparse.Namespace) -> int:
    try:
        payload = resolve_platform_context(
            project_root=Path(args.project_root),
            script_path=Path(__file__).resolve(),
        )
    except PlatformDetectionError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "command": _CMD_RESOLVE_PLATFORM_CONTEXT,
                    "current_state": "undetected",
                    "message": f"{exc}. Pause execution and wait for user direction.",
                },
                separators=(",", ":"),
            )
        )
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, separators=(",", ":")))
    return 0


def cmd_resolve_session_context(args: argparse.Namespace) -> int:
    try:
        plat = detect_platform(strict=False)
    except PlatformDetectionError:
        plat = "cursor"

    project_root = Path(args.project_root)
    conv_id = resolve_conversation_id(getattr(args, "conversation_id", None)) or ""
    entry = get_entry(project_root, plat, conv_id) if conv_id else None

    if entry is None:
        print(json.dumps(_empty_session_payload(conv_id), separators=(",", ":")))
        return 0

    cache_dir = resolve_cache_dir(project_root, plat)
    cycle_info = build_cycle_info(cache_dir, entry["cycle_id"])

    payload = _empty_session_payload(conv_id)
    payload["cycle_id"] = entry["cycle_id"]
    payload["cycle_type"] = entry.get("cycle_type", "feature")
    payload["stage"] = entry["stage"]
    if cycle_info is not None:
        payload["execution_mode"] = cycle_info.get("execution_mode", "guided")
    else:
        payload["execution_mode"] = "guided"

    print(json.dumps(payload, separators=(",", ":")))
    return 0


def cmd_set_execution_mode(args: argparse.Namespace) -> int:
    try:
        plat = detect_platform(strict=False)
    except PlatformDetectionError:
        plat = "cursor"

    facade_args = argparse.Namespace(
        project_root=Path(args.project_root).resolve(),
        platform=plat,
        cycle_id=args.cycle_id,
        mode=args.mode,
        internal=args.internal,
    )
    return cycle_cmd_set_execution_mode(facade_args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime bootstrap control.")
    parser.add_argument(
        "--project-root",
        type=Path,
        required=True,
        help="Project root directory.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    resolve_platform = sub.add_parser(
        _CMD_RESOLVE_PLATFORM_CONTEXT,
        help="Emit platform context JSON for session bootstrap",
    )
    resolve_platform.set_defaults(handler=cmd_resolve_platform_context)

    resolve_session = sub.add_parser(
        _CMD_RESOLVE_SESSION_CONTEXT,
        help="Emit session context JSON from active-context and cycles",
    )
    resolve_session.add_argument(
        "--conversation-id",
        default=None,
        help="Cursor/Copilot conversation ID (overrides LULU_CONVERSATION_ID).",
    )
    resolve_session.set_defaults(handler=cmd_resolve_session_context)

    set_mode = sub.add_parser(
        _CMD_SET_EXECUTION_MODE,
        help="Update execution_mode for one cycle (facade to cycle_control)",
    )
    set_mode.add_argument("--cycle-id", required=True, help="Cycle ID to update.")
    set_mode.add_argument(
        "--mode",
        required=True,
        choices=sorted({"guided", "autonomous"}),
        help="New execution mode.",
    )
    set_mode.add_argument(
        "--internal",
        action="store_true",
        help="Internal-only gate; required for set-execution-mode.",
    )
    set_mode.set_defaults(handler=cmd_set_execution_mode)

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
