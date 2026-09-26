#!/usr/bin/env python3
"""Runtime bootstrap control for lulu-dev-workflow.

Subcommands:
    resolve-platform-context   Emit platform context JSON for session bootstrap
    resolve-session-context    Emit session context JSON from active-context + cycles
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from active_context_schema import get_entry, resolve_conversation_id
from platform_schema import PlatformDetectionError, detect_platform, resolve_platform_context

_CMD_RESOLVE_PLATFORM_CONTEXT = "resolve-platform-context"
_CMD_RESOLVE_SESSION_CONTEXT = "resolve-session-context"


def _empty_session_payload(conversation_id: str = "") -> dict[str, str]:
    return {
        "conversation_id": conversation_id,
        "cycle_id": "",
        "cycle_type": "",
        "stage": "",
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

    payload = _empty_session_payload(conv_id)
    payload["cycle_id"] = entry["cycle_id"]
    payload["cycle_type"] = entry.get("cycle_type", "feature")
    payload["stage"] = entry["stage"]

    print(json.dumps(payload, separators=(",", ":")))
    return 0


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

    args = parser.parse_args()
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
