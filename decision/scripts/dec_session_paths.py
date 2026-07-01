#!/usr/bin/env python3
"""Session directory resolution for diagnostic (no holder path inference)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from dec_domain_constraints_schema import KERNEL_STAGE, load_domain_constraints


def default_cache_subdir(stage: str) -> str:
    if stage == KERNEL_STAGE:
        return KERNEL_STAGE
    return stage.replace("-", "/", 1)


def find_session_dir(project_root: Path, cycle_id: str, stage: str, cache_root: Path) -> Path | None:
    """Locate session dir by domain-constraints stage field under cache/cycle_id."""
    cycle_base = project_root / cache_root / cycle_id
    if not cycle_base.is_dir():
        return None
    for sub in cycle_base.iterdir():
        if not sub.is_dir():
            continue
        dc = sub / "domain-constraints.json"
        if not dc.is_file():
            continue
        try:
            data = json.loads(dc.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if str(data.get("stage", "")).strip() == stage:
            return sub
    return None


def session_cache_subdir(
    project_root: Path,
    cycle_id: str,
    stage: str,
    cache_root: Path,
    *,
    constraints_path: Optional[Path] = None,
) -> str:
    """Resolve cache subdir from existing session snapshot or explicit constraints path."""
    found = find_session_dir(project_root, cycle_id, stage, cache_root)
    if found is not None:
        dc = found / "domain-constraints.json"
        try:
            data = load_domain_constraints(dc)
            subdir = str(data.get("cache_subdir", "")).strip()
            if subdir:
                return subdir
        except (FileNotFoundError, ValueError):
            pass
    if constraints_path is not None:
        from dec_domain_constraints_schema import load_constraints_config

        cfg = load_constraints_config(constraints_path)
        subdir = str(cfg.get("cache_subdir", "")).strip()
        if subdir:
            return subdir
    return default_cache_subdir(stage)
