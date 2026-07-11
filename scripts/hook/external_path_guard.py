"""External path boundary guard for preToolUse externalPathGuard."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from session_paths import is_session_allowed


def resolve_path(path_str: str) -> Path:
    return Path(path_str).expanduser().resolve()


def is_outside_project(path: Path, project_root: Path) -> bool:
    try:
        path.resolve().relative_to(project_root.resolve())
        return False
    except ValueError:
        return True


def matches_allowlist(path_str: str, allowlist: List[str]) -> bool:
    target = resolve_path(path_str)
    for entry in allowlist:
        if not entry:
            continue
        try:
            target.relative_to(resolve_path(entry))
            return True
        except ValueError:
            continue
    return False


def check_external_write(
    targets: List[str],
    *,
    write_allow: List[str],
    session_allow: bool,
    session_id: str,
    platform: str,
) -> Optional[str]:
    """Return denied target path string, or None if all allowed."""
    for target in targets:
        if not target or not str(target).strip():
            continue
        if matches_allowlist(target, write_allow):
            continue
        if session_allow and is_session_allowed(target, session_id, platform):
            continue
        return target
    return None


def check_external_read(
    path: str,
    *,
    read_allow: List[str],
    session_allow: bool,
    session_id: str,
    platform: str,
) -> Optional[str]:
    """Return denied path string, or None if allowed."""
    if not path or not str(path).strip():
        return None
    if matches_allowlist(path, read_allow):
        return None
    if session_allow and is_session_allowed(path, session_id, platform):
        return None
    return path
