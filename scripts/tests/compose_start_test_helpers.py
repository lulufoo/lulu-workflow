#!/usr/bin/env python3
"""Shared helpers for tests that invoke compose ``start.py``."""

from __future__ import annotations

import json
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[2]


def write_scope_package(tmp_path: Path, source: Path | None = None) -> Path:
    """Write a scope-package.json whose source_path satisfies compose start's canonical check."""
    src = source if source is not None else (tmp_path / "scope-source.md")
    if not src.is_file():
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text("# scope\n", encoding="utf-8")
    path = tmp_path / "scope-package.json"
    path.write_text(
        json.dumps({"version": 2, "source_path": str(src.resolve())}, indent=2) + "\n",
        encoding="utf-8",
    )
    return path.resolve()


def compose_start_args(
    profile_id: str,
    tmp_path: Path,
    source: Path | None = None,
    *extra: str,
) -> list[str]:
    """CLI args required by compose ``start.py`` beyond --project-root and --cycle-id."""
    scope = write_scope_package(tmp_path, source)
    return [
        "--profile-path",
        str(_WORKFLOW_ROOT / profile_id / "compose-profile.json"),
        "--scope-package",
        str(scope),
        *extra,
    ]
