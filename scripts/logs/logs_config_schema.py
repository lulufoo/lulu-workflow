#!/usr/bin/env python3
"""Logs switch + output dir helpers (reads ``logs`` from workflow-guard-config)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
HOOK_DIR = SCRIPTS_DIR / "hook"
for _path in (SCRIPTS_DIR, HOOK_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from hook_config_schema import is_logs_enabled  # noqa: E402
from platforms.paths import cache_dir as platform_cache_dir  # noqa: E402
from workflow_config_schema import detect_platform  # noqa: E402

_LOGS_SUBDIR = ".logs"

__all__ = ["is_logs_enabled", "resolve_logs_dir"]


def resolve_logs_dir(
    project_root: Path,
    platform: Optional[str] = None,
) -> Path:
    """Return ``.cache/{platform}/lulu-workflow/.logs`` under project_root."""
    plat = detect_platform(platform)
    return (project_root / platform_cache_dir(plat) / _LOGS_SUBDIR).resolve()
