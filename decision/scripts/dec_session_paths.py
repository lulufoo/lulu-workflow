#!/usr/bin/env python3
"""Session directory resolution for decision (no holder path inference)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from dec_domain_constraints_schema import load_domain_constraints

_APPROACH_DX_DIR_PAT = re.compile(r"^D\d+$")


def default_cache_subdir(stage: str) -> str:
    return stage


def _domain_constraints_stage(session_dir: Path) -> str | None:
    dc = session_dir / "domain-constraints.json"
    if not dc.is_file():
        return None
    try:
        data = json.loads(dc.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    return str(data.get("stage", "")).strip() or None


def find_session_dir(project_root: Path, cycle_id: str, stage: str, cache_root: Path) -> Path | None:
    """Locate session dir by domain-constraints stage field under cache/cycle_id.

    For ``lulu-approach``, prefer ``<stage>/main`` when its domain-constraints
    match; also discovers nested ``Dx/`` session roots. When multiple nested
    sessions match and no explicit ``session_dir`` is provided, prefer ``main``.
    Flat ``<stage>/domain-constraints.json`` remains supported for back-compat.
    """
    cycle_base = project_root / cache_root / cycle_id
    if not cycle_base.is_dir():
        return None

    if stage == "lulu-approach":
        stage_dir = cycle_base / default_cache_subdir(stage)
        if stage_dir.is_dir():
            matches: list[Path] = []
            main_dir = stage_dir / "main"
            if _domain_constraints_stage(main_dir) == stage:
                matches.append(main_dir)
            for child in sorted(stage_dir.iterdir()):
                if (
                    child.is_dir()
                    and _APPROACH_DX_DIR_PAT.match(child.name)
                    and _domain_constraints_stage(child) == stage
                ):
                    matches.append(child)
            if matches:
                for candidate in matches:
                    if candidate.name == "main":
                        return candidate
                if len(matches) == 1:
                    return matches[0]
                return None
            if _domain_constraints_stage(stage_dir) == stage:
                return stage_dir

    for sub in cycle_base.iterdir():
        if not sub.is_dir():
            continue
        if _domain_constraints_stage(sub) == stage:
            return sub
    return None


def parse_session_dir_arg(raw: str | None, project_root: Path) -> Path | None:
    """Parse ``--session-dir``; when set, skip ``find_session_dir`` (P1.1 A)."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = (project_root / candidate).resolve()
    else:
        candidate = candidate.resolve()
    return candidate


def session_artifact_paths(session_dir: Path) -> dict[str, Path]:
    """Artifact paths under an explicit nested session root."""
    base = session_dir
    return {
        "session_dir": base,
        "session_state": base / "session-state.md",
        "gate_state": base / "gate-state.json",
        "registers": base / "registers.json",
        "decision_doc": base / "decision-doc.md",
        "payloads_dir": base / "gate-payloads",
        "domain_constraints": base / "domain-constraints.json",
    }


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
