#!/usr/bin/env python3
"""Schema and I/O for cycle-log.md — cross-stage append-only audit/troubleshooting log."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

_VALID_LEVELS = frozenset({"INFO", "WARN", "ERROR"})
_LOG_FILENAME = "cycle-log.md"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log_path(cycle_dir: Path) -> Path:
    """Return path to cycle-log.md under the cycle cache directory."""
    return cycle_dir / _LOG_FILENAME


def append_cycle_log(cycle_dir: Path, level: str, stage: str, message: str) -> None:
    """Append one line to <cycle_dir>/cycle-log.md. Never raises on I/O failure."""
    level_upper = level.strip().upper()
    if level_upper not in _VALID_LEVELS:
        raise ValueError(f"invalid log level: {level!r} (allowed: {sorted(_VALID_LEVELS)})")

    safe_message = " ".join(message.splitlines())
    line = f"{_timestamp()} [{level_upper}] {stage} {safe_message}\n"

    try:
        path = log_path(cycle_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass
