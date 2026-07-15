"""Internal path guard helpers for preToolUse internalPathGuard."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

_WRITE_TOOL_NAMES = frozenset({"Write", "Edit"})
_READ_TOOL_NAMES = frozenset({"Read"})
_RW_TOOL_NAMES = _WRITE_TOOL_NAMES | _READ_TOOL_NAMES


def normalize_tool_path(raw_path: str, project_root: Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        try:
            return (
                project_root / candidate.resolve().relative_to(project_root.resolve())
            ).resolve()
        except ValueError:
            return candidate.resolve()
    return (project_root / candidate).resolve()


def resolve_allowed_dirs(project_root: Path, dir_templates: list[str]) -> list[Path]:
    roots: list[Path] = []
    for item in dir_templates:
        if item in (".", "./"):
            roots.append(project_root.resolve())
        else:
            roots.append((project_root / item).resolve())
    return roots


def path_under_any_allowed(target: Path, allowed_roots: list[Path]) -> bool:
    resolved = target.resolve()
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def extract_tool_path(tool_name: str, tool_input: object) -> Optional[str]:
    if not isinstance(tool_input, dict):
        return None
    raw = (
        tool_input.get("path")
        or tool_input.get("target_file")
        or tool_input.get("file_path")
        or tool_input.get("filePath")
        or ""
    )
    if not raw:
        return None
    return str(raw)


def is_rw_tool(tool_name: str) -> bool:
    return tool_name in _RW_TOOL_NAMES


def is_write_tool(tool_name: str) -> bool:
    return tool_name in _WRITE_TOOL_NAMES


def allowed_dirs_for_tool(
    tool_name: str,
    *,
    read_dirs: list[str],
    write_dirs: list[str],
) -> list[str]:
    if tool_name in _READ_TOOL_NAMES:
        return read_dirs
    if tool_name in _WRITE_TOOL_NAMES:
        return write_dirs
    return []
