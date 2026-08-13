"""Platform detection and path SSOT for lulu-dev-workflow."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

SKILL_NAME = "lulu-dev-workflow"
SUPPORTED_PLATFORMS = ("cursor", "copilot", "claude")

PLATFORM_PATHS: dict[str, dict[str, Path]] = {
    "cursor": {
        "workflow_dir": Path(".cursor/lulu-dev-workflow"),
        "cache_dir": Path(".cache/cursor/lulu-dev-workflow"),
    },
    "copilot": {
        "workflow_dir": Path(".github/lulu-dev-workflow"),
        "cache_dir": Path(".cache/copilot/lulu-dev-workflow"),
    },
    "claude": {
        "workflow_dir": Path(".claude/lulu-dev-workflow"),
        "cache_dir": Path(".cache/claude/lulu-dev-workflow"),
    },
}


class PlatformDetectionError(Exception):
    """Raised when platform cannot be detected and no override is available."""


def _normalize_platform(value: str) -> str:
    plat = value.strip().lower()
    if plat not in SUPPORTED_PLATFORMS:
        raise PlatformDetectionError(f"unsupported platform: {value!r}")
    return plat


def _signal_platform() -> Optional[str]:
    if os.environ.get("VSCODE_TARGET_SESSION_LOG") or os.environ.get("COPILOT_AGENT") == "1":
        return "copilot"
    if os.environ.get("CURSOR_AGENT"):
        return "cursor"
    if os.environ.get("CLAUDE_CODE"):
        return "claude"
    return None


def detect_platform(*, override: Optional[str] = None, strict: bool = False) -> str:
    """Detect active platform from override, env override, or runtime signals."""
    if override:
        return _normalize_platform(override)

    lulu_platform = os.environ.get("LULU_PLATFORM")
    if lulu_platform:
        return _normalize_platform(lulu_platform)

    detected = _signal_platform()
    if detected:
        return detected

    if strict:
        raise PlatformDetectionError("No platform signal matched.")
    return "cursor"


def resolve_skill_root(*, script_path: Path) -> Path:
    """Return skill root directory from a script under scripts/."""
    return script_path.resolve().parent.parent


def resolve_platform_context(
    *,
    project_root: Path,
    script_path: Path,
) -> dict[str, str]:
    """Build resolve-platform-context stdout payload."""
    root = project_root.resolve()
    plat = detect_platform(strict=False)
    paths = PLATFORM_PATHS[plat]
    skill_root = resolve_skill_root(script_path=script_path)
    return {
        "platform": plat,
        "project_root": str(root),
        "skill_root": str(skill_root),
        "workflow_dir": paths["workflow_dir"].as_posix(),
        "cache_dir": paths["cache_dir"].as_posix(),
    }
