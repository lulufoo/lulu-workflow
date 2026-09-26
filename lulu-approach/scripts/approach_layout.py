#!/usr/bin/env python3
"""Approach session layout helpers.

The decision session is the approach root. The root also holds the package
and the shell pointer.
Package paths are relative to the root and must not escape it.
"""

from __future__ import annotations

from pathlib import Path

DECISION_PACKAGE_FILENAME = "decision-package.json"
SOURCE_PACKAGE_FILENAME = "source-package.json"
APPROACH_CACHE_SUBDIR = "lulu-approach"


def decision_package_path(approach_root: Path) -> Path:
    """Path to ``decision-package.json`` at the approach root."""
    return Path(approach_root).resolve() / DECISION_PACKAGE_FILENAME


def source_package_path(approach_root: Path) -> Path:
    """Path to delivered ``source-package.json`` at the approach root."""
    return Path(approach_root).resolve() / SOURCE_PACKAGE_FILENAME


def ensure_approach_layout(approach_root: Path) -> Path:
    """Create the approach root and return it resolved.

    Does not create ``decision-package.json``.
    """
    root = Path(approach_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def is_rel_path_under_approach(rel_path: str) -> bool:
    """True when ``rel_path`` is a non-empty relative path with no ``..``."""
    text = str(rel_path).strip()
    if not text or text.startswith("/"):
        return False
    return ".." not in Path(text).parts


def resolve_under_approach(approach_root: Path, rel_path: str) -> Path:
    """Resolve ``rel_path`` under approach root; reject escapes."""
    if not is_rel_path_under_approach(rel_path):
        raise ValueError(
            f"path must be relative under approach root (no '..' / absolute): {rel_path!r}"
        )
    root = Path(approach_root).resolve()
    target = (root / str(rel_path).strip()).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes approach root: {rel_path!r}") from exc
    return target


def relpath_from_approach(approach_root: Path, target: Path) -> str:
    """Return posix path of ``target`` relative to approach root; reject outside."""
    root = Path(approach_root).resolve()
    resolved = Path(target).resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path outside approach root: {target}") from exc
    text = rel.as_posix()
    if not is_rel_path_under_approach(text):
        raise ValueError(f"path outside approach root: {target}")
    return text
