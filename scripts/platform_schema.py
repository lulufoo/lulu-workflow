#!/usr/bin/env python3
"""Backward-compatible re-export of platforms.registry.

Library module — CLI lives in runtime_control.py.
"""

from platforms.registry import (  # noqa: F401
    PLATFORM_PATHS,
    SKILL_NAME,
    SUPPORTED_PLATFORMS,
    PlatformDetectionError,
    detect_platform,
    resolve_platform_context,
    resolve_skill_root,
)
