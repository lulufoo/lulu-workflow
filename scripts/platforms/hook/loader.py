"""Dynamic loader for preToolUse hook platform adapters."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from platforms.paths import HOOK_PLATFORMS
from platforms.registry import PlatformDetectionError, _normalize_platform

_HOOK_DIR = Path(__file__).resolve().parent


def load_hook_adapter(platform: str):
    """Load platforms/hook/{platform}.py as a module."""
    plat = _normalize_platform(platform)
    if plat not in HOOK_PLATFORMS:
        raise PlatformDetectionError(f"hook adapter not available for platform: {plat!r}")
    path = _HOOK_DIR / f"{plat}.py"
    spec = importlib.util.spec_from_file_location(f"platforms.hook.{plat}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
