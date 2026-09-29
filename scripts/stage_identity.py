"""Canonical exec-stage name plus legacy lulu-code cache/config aliases."""

from __future__ import annotations

from pathlib import Path

EXEC_STAGE = "lulu-exec"
EXEC_STAGE_LEGACY = "lulu-code"

_STAGE_ALIASES = {
    EXEC_STAGE: (EXEC_STAGE, EXEC_STAGE_LEGACY),
    EXEC_STAGE_LEGACY: (EXEC_STAGE, EXEC_STAGE_LEGACY),
}


def stage_config_aliases(stage: str) -> tuple[str, ...]:
    """Return lookup names for a stage, modern name first."""
    return _STAGE_ALIASES.get(stage, (stage,))


def exec_stage_dir(cycle_dir: Path, *, migrate: bool = False) -> Path:
    """Return the exec-stage cache dir, preferring lulu-exec over lulu-code."""
    cycle = Path(cycle_dir)
    modern = cycle / EXEC_STAGE
    legacy = cycle / EXEC_STAGE_LEGACY
    if migrate and not modern.exists() and legacy.exists():
        legacy.rename(modern)
        return modern
    if modern.exists():
        return modern
    if legacy.exists():
        return legacy
    return modern


def migrate_exec_stage_dir(cycle_dir: Path) -> Path:
    """Rename leftover lulu-code/ to lulu-exec/ when the modern dir is absent."""
    dest = exec_stage_dir(cycle_dir, migrate=True)
    _rewrite_workflow_state_paths(dest)
    return dest


def _rewrite_workflow_state_paths(stage_dir: Path) -> None:
    """Point migrated workflow-state refs at the new cache subdirectory."""
    if not stage_dir.is_dir():
        return
    needle = f"/{EXEC_STAGE_LEGACY}/"
    repl = f"/{EXEC_STAGE}/"
    for path in stage_dir.glob("s*/workflow-state.md"):
        text = path.read_text(encoding="utf-8")
        updated = text.replace(needle, repl)
        if updated != text:
            path.write_text(updated, encoding="utf-8")


def resolve_stage_cache_dir(cache_dir: Path, cycle_id: str, stage: str) -> Path:
    """Return the on-disk stage cache directory, with exec-stage aliasing."""
    cycle = Path(cache_dir) / cycle_id
    if stage in _STAGE_ALIASES:
        return exec_stage_dir(cycle)
    return cycle / stage
