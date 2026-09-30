"""Canonical exec-stage name and cache directory."""

from __future__ import annotations

from pathlib import Path

EXEC_STAGE = "lulu-exec"


def exec_stage_dir(cycle_dir: Path) -> Path:
    """Return the exec-stage cache dir."""
    return Path(cycle_dir) / EXEC_STAGE


def resolve_stage_cache_dir(cache_dir: Path, cycle_id: str, stage: str) -> Path:
    """Return the on-disk stage cache directory."""
    return Path(cache_dir) / cycle_id / stage
