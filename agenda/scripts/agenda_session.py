#!/usr/bin/env python3
"""Resolve revision dir from compose session records (no compose package import).

Uses cycle cache + ``.compose-profile-path`` + ``session-state.md`` ``active_doc``
→ ``revision{N}/`` — same records ``session_control`` / start already write.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_AGENDA_SCRIPTS = Path(__file__).resolve().parent
_WORKFLOW_ROOT = _AGENDA_SCRIPTS.parents[1]
_WORKFLOW_SCRIPTS = _WORKFLOW_ROOT / "scripts"
if str(_WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_WORKFLOW_SCRIPTS))

from archive_common import CACHE_DIR, read_md_field  # noqa: E402

PROFILE_POINTER_NAME = ".compose-profile-path"


def resolve_cycle_id(explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    env_val = os.environ.get("LULU_CYCLE_ID", "").strip()
    if env_val:
        return env_val
    raise ValueError(
        "cycle-id required: pass --cycle-id or set LULU_CYCLE_ID "
        "(after Session Foundation / start)"
    )


def _load_profile_id(profile_json: Path) -> str:
    data = json.loads(profile_json.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"compose profile must be an object: {profile_json}")
    return str(data.get("profile_id", "")).strip()


def _read_pointer_target(session_base: Path, project_root: Path) -> Path:
    pointer = session_base / PROFILE_POINTER_NAME
    raw = pointer.read_text(encoding="utf-8").strip()
    if not raw:
        raise ValueError(f"empty compose profile pointer: {pointer}")
    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate
    else:
        resolved = (project_root / candidate).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(
            f"compose profile pointer targets missing file: {resolved}"
        )
    return resolved


def resolve_session_base(
    project_root: Path,
    cycle_id: str,
    profile_id: str,
) -> Path:
    """Locate session base dir that owns ``.compose-profile-path`` for profile_id."""
    root = project_root.resolve()
    pid = profile_id.strip()
    cid = cycle_id.strip()
    cycle_dir = root / CACHE_DIR / cid
    if not cycle_dir.is_dir():
        raise FileNotFoundError(
            f"cycle cache not found: {cycle_dir}. Run stage start first."
        )
    for pointer in sorted(cycle_dir.rglob(PROFILE_POINTER_NAME)):
        session_base = pointer.parent
        try:
            profile_path = _read_pointer_target(session_base, root)
            if _load_profile_id(profile_path) == pid:
                return session_base
        except (OSError, json.JSONDecodeError, ValueError, FileNotFoundError):
            continue
    raise FileNotFoundError(
        f"no compose profile pointer for {pid!r} under cycle {cid!r} ({cycle_dir})"
    )


def load_active_doc(session_base: Path, *, default: int = 1) -> int:
    ss = session_base / "session-state.md"
    if not ss.is_file():
        return default
    raw = read_md_field(ss, "active_doc", default="")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"active_doc must be an integer in {ss}, got {raw!r}") from exc


def resolve_revision_dir(
    project_root: Path,
    *,
    cycle_id: str | None = None,
    profile_id: str,
) -> Path:
    """Return absolute ``…/revision{active_doc}/`` for the active compose session."""
    cid = resolve_cycle_id(cycle_id)
    pid = profile_id.strip()
    if not pid:
        raise ValueError("--profile is required when resolving session revision")
    session_base = resolve_session_base(project_root, cid, pid)
    active_doc = load_active_doc(session_base)
    revision_dir = session_base / f"revision{active_doc}"
    if not revision_dir.is_dir():
        raise FileNotFoundError(
            f"revision dir not found: {revision_dir} "
            f"(session-state active_doc={active_doc})"
        )
    return revision_dir
