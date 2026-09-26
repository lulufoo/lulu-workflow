#!/usr/bin/env python3
"""Append-only workflow log emitters (io.log / biz.log)."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from active_context_schema import resolve_conversation_id  # noqa: E402
from logs.logs_config_schema import (  # noqa: E402
    is_logs_enabled,
    resolve_logs_dir,
)
from workflow_config_schema import detect_platform  # noqa: E402

_IO_LOG_NAME = "io.log"
_BIZ_LOG_NAME = "biz.log"
_MONO_ORIGIN = time.monotonic()


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _mono_ms() -> int:
    return int((time.monotonic() - _MONO_ORIGIN) * 1000)


def _resolve_conv_id(conversation_id: Optional[str]) -> str:
    resolved = resolve_conversation_id(conversation_id)
    return (resolved or "unknown").strip() or "unknown"


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def emit_io(
    *,
    project_root: Path,
    conversation_id: Optional[str],
    action: str,
    tool: str,
    path: str,
    platform: Optional[str] = None,
) -> None:
    """Append one Hook I/O record to ``io.log``. Best-effort; never raises."""
    try:
        root = Path(project_root).resolve()
        plat = detect_platform(platform)
        if not is_logs_enabled(root, plat):
            return
        record = {
            "ts": _iso_now(),
            "mono_ms": _mono_ms(),
            "conv_id": _resolve_conv_id(conversation_id),
            "kind": "io",
            "action": str(action or "").strip() or "unknown",
            "tool": str(tool or "").strip() or "unknown",
            "path": str(path or ""),
        }
        _append_jsonl(resolve_logs_dir(root, plat) / _IO_LOG_NAME, record)
    except Exception:
        return


def emit_biz(
    *,
    component: str,
    event: str,
    conversation_id: Optional[str] = None,
    project_root: Optional[Path] = None,
    platform: Optional[str] = None,
    detail: Optional[dict[str, Any]] = None,
) -> None:
    """Append one business event to ``biz.log``. Best-effort; never raises."""
    try:
        root = Path(project_root or Path.cwd()).resolve()
        plat = detect_platform(platform)
        if not is_logs_enabled(root, plat):
            return
        record: dict[str, Any] = {
            "ts": _iso_now(),
            "mono_ms": _mono_ms(),
            "conv_id": _resolve_conv_id(conversation_id),
            "kind": "biz",
            "component": str(component or "").strip() or "unknown",
            "event": str(event or "").strip() or "unknown",
        }
        if detail:
            record["detail"] = detail
        _append_jsonl(resolve_logs_dir(root, plat) / _BIZ_LOG_NAME, record)
    except Exception:
        return
