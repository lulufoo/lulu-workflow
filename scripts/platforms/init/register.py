"""Dispatch init-project hook registration by platform."""

from __future__ import annotations

from pathlib import Path

from platforms.init.claude import register_claude_hook
from platforms.init.copilot import register_copilot_hook
from platforms.init.cursor import register_cursor_hook
from platforms.paths import hook_guard_command
from platforms.registry import PlatformDetectionError, _normalize_platform

_REGISTRARS = {
    "cursor": register_cursor_hook,
    "copilot": register_copilot_hook,
    "claude": register_claude_hook,
}


def register_hook(project_root: Path, platform: str) -> str:
    """Register platform hook config; return the hook command registered."""
    plat = _normalize_platform(platform)
    registrar = _REGISTRARS.get(plat)
    if registrar is None:
        raise PlatformDetectionError(f"no hook registrar for platform: {plat!r}")
    registrar(project_root)
    return hook_guard_command(plat)
