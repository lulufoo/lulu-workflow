"""Active compose profile for kernel modules (section registry, round control)."""

from __future__ import annotations

from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID

_ACTIVE_PROFILE: str = DEFAULT_COMPOSE_PROFILE_ID


def set_active_profile(profile_id: str) -> None:
    """Set compose profile / stage name for the current process."""
    global _ACTIVE_PROFILE
    _ACTIVE_PROFILE = profile_id.strip() or DEFAULT_COMPOSE_PROFILE_ID


def reset_active_profile() -> None:
    """Restore default compose profile (lulu-plan) for test isolation."""
    global _ACTIVE_PROFILE
    _ACTIVE_PROFILE = DEFAULT_COMPOSE_PROFILE_ID


def get_active_profile() -> str:
    """Return active compose profile id (defaults to lulu-plan)."""
    return _ACTIVE_PROFILE
