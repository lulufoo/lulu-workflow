#!/usr/bin/env python3
"""beforeSubmitPrompt entry for externalPathGuard.sessionAllow."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HOOK_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _HOOK_DIR.parent
for path in (_HOOK_DIR, _SCRIPTS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from hook_config_schema import resolve_external_path_guard  # noqa: E402
from session_paths import (  # noqa: E402
    add_session_paths,
    cleanup_old_session_files,
    collect_eligible_paths,
    session_paths_root,
)


def _read_payload() -> dict:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        return payload if isinstance(payload, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def handle_before_submit_prompt(payload: dict, *, platform: str) -> None:
    guard = resolve_external_path_guard(Path.cwd(), platform=platform)
    if not guard.get("enabled") or not guard.get("sessionAllow"):
        return
    session_id = (payload.get("conversation_id") or "unknown").strip() or "unknown"
    prompt = payload.get("prompt") or ""
    attachments = payload.get("attachments")
    eligible = collect_eligible_paths(
        prompt=str(prompt),
        attachments=attachments,
        workspace_root=Path.cwd().resolve(),
    )
    add_session_paths(session_id, eligible, platform=platform)
    cleanup_old_session_files(session_paths_root(platform))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="lulu-dev-workflow prompt hook for externalPathGuard.sessionAllow"
    )
    parser.add_argument("--platform", default="cursor", choices=["cursor", "copilot", "claude"])
    args = parser.parse_args()
    handle_before_submit_prompt(_read_payload(), platform=args.platform)
    print(json.dumps({"continue": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
