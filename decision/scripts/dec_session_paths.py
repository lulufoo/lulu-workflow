#!/usr/bin/env python3
"""Session directory resolution for decision (no holder path inference)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from dec_domain_constraints_schema import load_domain_constraints


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
    """Locate the cycle child whose domain-constraints stage matches."""
    cycle_base = project_root / cache_root / cycle_id
    if not cycle_base.is_dir():
        return None
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


def stage_outer_root(
    project_root: Path,
    cycle_id: str,
    stage: str,
    cache_root: Path,
    *,
    constraints_path: Optional[Path] = None,
) -> Path:
    """Stage outer root where ``active-session.json`` lives (archive-1.1 A5)."""
    subdir = session_cache_subdir(
        project_root,
        cycle_id,
        stage,
        cache_root,
        constraints_path=constraints_path,
    )
    return (project_root / cache_root / cycle_id / subdir).resolve()


def resolve_active_session_dir(stage_outer: Path) -> Path:
    """Resolve Active Session absolute path; raise if missing/invalid."""
    from dec_active_session_schema import (  # noqa: WPS433
        is_valid_session_root,
        load_active_session,
    )

    outer = Path(stage_outer).resolve()
    data = load_active_session(outer)
    rel = str(data["session_dir"])
    if rel == ".":
        target = outer
    else:
        target = (outer / rel).resolve()
        try:
            target.relative_to(outer)
        except ValueError as exc:
            raise ValueError(
                f"active session_dir escapes stage outer: {rel!r}"
            ) from exc
    if not is_valid_session_root(target):
        raise ValueError(
            f"active session root is not a valid decision session: {target}"
        )
    return target


def resolve_session_root_for_command(
    project_root: Path,
    cycle_id: str,
    stage: str,
    cache_root: Path,
    *,
    constraints_path: Optional[Path] = None,
    session_dir: Optional[Path] = None,
) -> Path:
    """Resolve session root for daily commands (A3=B′): Active only.

    ``session_dir`` is for internal Python callers (e.g. init-session / tests).
    """
    if session_dir is not None:
        return Path(session_dir).resolve()
    outer = stage_outer_root(
        project_root,
        cycle_id,
        stage,
        cache_root,
        constraints_path=constraints_path,
    )
    return resolve_active_session_dir(outer)
