#!/usr/bin/env python3
"""Nested approach session layout helpers (archive-1.0 P2.dirs).

Outer root ``…/lulu-approach/`` holds package / pointer / internal DAG only.
``main/`` and optional ``Dx/`` are complete decision session subtrees (D1–D3).
Package paths are relative to the outer root and must not escape it (D4).
"""

from __future__ import annotations

import re
from pathlib import Path

DECISION_PACKAGE_FILENAME = "decision-package.json"
MAIN_DIRNAME = "main"
APPROACH_CACHE_SUBDIR = "lulu-approach"
_DX_ID_RE = re.compile(r"^D\d+$")


def main_session_dir(approach_root: Path) -> Path:
    """Absolute path to the always-present ``main/`` session (D3)."""
    return Path(approach_root).resolve() / MAIN_DIRNAME


def dx_session_dir(approach_root: Path, node_id: str) -> Path:
    """Absolute path to a ``Dx/`` child session directory."""
    sid = str(node_id).strip()
    if not _DX_ID_RE.match(sid):
        raise ValueError(f"node_id must match D<number>, got {node_id!r}")
    return Path(approach_root).resolve() / sid


def decision_package_path(approach_root: Path) -> Path:
    """Path to ``decision-package.json`` at the outer approach root."""
    return Path(approach_root).resolve() / DECISION_PACKAGE_FILENAME


def ensure_approach_layout(
    approach_root: Path,
    *,
    dx_ids: list[str] | None = None,
) -> Path:
    """Create outer root + ``main/`` (+ optional ``Dx/``); return resolved root.

    Does not write session artifacts (gate-state, etc.) into the outer root.
    Does not create ``decision-package.json`` (written at Delivered / package time).
    """
    root = Path(approach_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    main_session_dir(root).mkdir(parents=True, exist_ok=True)
    for node_id in dx_ids or []:
        dx_session_dir(root, node_id).mkdir(parents=True, exist_ok=True)
    return root


def approach_root_from_session_dir(session_dir: Path) -> Path:
    """Resolve outer approach root from a ``main/`` or ``Dx/`` session dir."""
    session = Path(session_dir).resolve()
    name = session.name
    if name != MAIN_DIRNAME and not _DX_ID_RE.match(name):
        raise ValueError(
            f"session_dir must be main/ or Dx/, got {session}"
        )
    return session.parent


def is_rel_path_under_approach(rel_path: str) -> bool:
    """True when ``rel_path`` is a non-empty relative path with no ``..`` (D4)."""
    text = str(rel_path).strip()
    if not text or text.startswith("/"):
        return False
    return ".." not in Path(text).parts


def resolve_under_approach(approach_root: Path, rel_path: str) -> Path:
    """Resolve ``rel_path`` under approach root; reject escapes (D4)."""
    if not is_rel_path_under_approach(rel_path):
        raise ValueError(
            f"path must be relative under approach root (no '..' / absolute): {rel_path!r}"
        )
    root = Path(approach_root).resolve()
    target = (root / str(rel_path).strip()).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"path escapes approach root: {rel_path!r}"
        ) from exc
    return target


def relpath_from_approach(approach_root: Path, target: Path) -> str:
    """Return posix path of ``target`` relative to approach root; reject outside."""
    root = Path(approach_root).resolve()
    resolved = Path(target).resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"path outside approach root: {target}"
        ) from exc
    text = rel.as_posix()
    if not is_rel_path_under_approach(text):
        raise ValueError(f"path outside approach root: {target}")
    return text
