#!/usr/bin/env python3
"""Resolve codebase SoT ref.root and strategy for eval probe runners."""

from __future__ import annotations

from pathlib import Path

_VALID_STRATEGIES = frozenset({"all"})


class CodebaseSotError(Exception):
    """Raised when codebase ref cannot be resolved."""


def resolve_root(root: str, *, project_root: Path) -> Path:
    """Resolve codebase root; '.' means project_root."""
    root = root.strip()
    if not root:
        raise CodebaseSotError("empty root")
    if root in (".", "./"):
        return project_root.resolve()
    path = Path(root)
    if path.is_absolute():
        if not path.is_dir():
            raise CodebaseSotError(f"root not found: {path}")
        return path
    resolved = (project_root / path).resolve()
    if not resolved.is_dir():
        raise CodebaseSotError(f"root not found: {resolved}")
    return resolved


def validate_strategy(strategy: str) -> None:
    """Raise CodebaseSotError when strategy is unsupported."""
    if strategy not in _VALID_STRATEGIES:
        raise CodebaseSotError(
            f"unsupported strategy: {strategy!r} (allowed: {sorted(_VALID_STRATEGIES)})",
        )


def resolve_codebase_ref(
    ref: dict[str, str],
    *,
    project_root: Path,
) -> tuple[Path, str]:
    """Return (repo_root, strategy) from a codebase sot ref object."""
    if not isinstance(ref, dict):
        raise CodebaseSotError("codebase ref must be an object")
    root = ref.get("root", "")
    strategy = ref.get("strategy", "")
    if not isinstance(root, str) or not isinstance(strategy, str):
        raise CodebaseSotError("root and strategy must be strings")
    validate_strategy(strategy.strip())
    return resolve_root(root, project_root=project_root), strategy.strip()
