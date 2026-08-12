#!/usr/bin/env python3
"""Hook-side dispatch entry for workflow I/O logging.

Called from ``hook_guard.py`` only — not registered as a separate hooks.json entry.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
HOOK_DIR = SCRIPTS_DIR / "hook"
for _path in (SCRIPTS_DIR, HOOK_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from internal_path_guard import is_write_tool  # noqa: E402
from logs.workflow_log import emit_io  # noqa: E402


def maybe_log_tool_io(
    *,
    project_root: Path,
    platform: str,
    conversation_id: str,
    tool_name: str,
    path: str,
) -> None:
    """Log Read/Write/Edit tool I/O when enabled. Never raises; never denies."""
    try:
        name = str(tool_name or "").strip()
        if name not in ("Read", "Write", "Edit"):
            return
        action = "write" if is_write_tool(name) else "read"
        emit_io(
            project_root=project_root,
            platform=platform,
            conversation_id=conversation_id,
            action=action,
            tool=name,
            path=path,
        )
    except Exception:
        return
