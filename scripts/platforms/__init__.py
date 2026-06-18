"""Cross-platform registry, paths, hook adapters, and init registration."""

from platforms.registry import (  # noqa: F401
    PLATFORM_PATHS,
    SKILL_NAME,
    SUPPORTED_PLATFORMS,
    PlatformDetectionError,
    detect_platform,
    resolve_platform_context,
    resolve_skill_root,
)
