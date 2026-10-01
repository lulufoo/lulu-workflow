"""Platform detection and path SSOT for lulu-workflow."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

SKILL_NAME = "lulu-workflow"
SUPPORTED_PLATFORMS = ("cursor", "copilot", "claude")

PLATFORM_PATHS: dict[str, dict[str, Path]] = {
    "cursor": {
        "workflow_dir": Path(".cursor/lulu-workflow"),
        "cache_dir": Path(".cache/cursor/lulu-workflow"),
    },
    "copilot": {
        "workflow_dir": Path(".github/lulu-workflow"),
        "cache_dir": Path(".cache/copilot/lulu-workflow"),
    },
    "claude": {
        "workflow_dir": Path(".claude/lulu-workflow"),
        "cache_dir": Path(".cache/claude/lulu-workflow"),
    },
}

AGENTS_WORKFLOW_DIR = Path(".agents/config/lulu-workflow")
LEGACY_WORKFLOW_DIRS = {
    platform: paths["workflow_dir"] for platform, paths in PLATFORM_PATHS.items()
}


def resolve_workflow_dir(platform: str, project_root: Optional[Path] = None) -> Path:
    """Platform-neutral .agents/config dir wins; legacy per-platform dir is fallback.

    Existence is probed under project_root when given, else under the CWD.
    Returns the workflow dir relative to that base.
    """
    base = project_root if project_root is not None else Path(".")
    if (base / AGENTS_WORKFLOW_DIR).is_dir():
        return AGENTS_WORKFLOW_DIR
    legacy = LEGACY_WORKFLOW_DIRS.get(platform, LEGACY_WORKFLOW_DIRS["cursor"])
    if (base / legacy).is_dir():
        return legacy
    return AGENTS_WORKFLOW_DIR


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
    skill_root = resolve_skill_root(script_path=script_path)
    return {
        "platform": plat,
        "project_root": str(root),
        "skill_root": str(skill_root),
        "workflow_dir": resolve_workflow_dir(plat, root).as_posix(),
        "cache_dir": PLATFORM_PATHS[plat]["cache_dir"].as_posix(),
    }
