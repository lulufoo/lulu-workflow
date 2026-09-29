"""Session scanning and terminal/delivered state for lulu-workflow cache layouts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from stage_identity import resolve_stage_cache_dir

_VALID_STATES = frozenset(
    {"Drafting", "Working", "Evaluating", "TDABlocked", "Delivered", "Invalidated"}
)

STAGE_FLAT = frozenset({"decision", "lulu-bet", "lulu-approach"})
# Decision-family node/session terminal is Completed; legacy Delivered accepted on read.
_FLAT_VALID_STATES = frozenset(
    {"InProgress", "Frozen", "Completed", "Delivered", "Invalidated"}
)
_FLAT_SESSION_TERMINAL = frozenset({"Completed", "Delivered"})
_STAGE_REVISION_PAT = re.compile(r"^(revision|r|s)\d+$")
_APPROACH_DX_DIR_PAT = re.compile(r"^D\d+$")

_STAGE_FLAT = STAGE_FLAT


def stage_subdir(stage: str) -> str:
    """Return cache subdirectory for stage (flat id, e.g. lulu-design)."""
    return stage


_stage_subdir = stage_subdir


def parse_frontmatter(text: str) -> dict:
    """Extract key: value pairs from YAML frontmatter block."""
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    result = {}
    for line in match.group(1).splitlines():
        kv = re.match(r"^(\w[\w_-]*):\s*(.*)", line)
        if kv:
            result[kv.group(1)] = kv.group(2).strip()
    return result


_parse_frontmatter = parse_frontmatter


@dataclass
class SessionInfo:
    revision: str
    state: str
    created_at: str
    state_path: Optional[Path] = None


def _append_flat_session(
    sessions: List[SessionInfo],
    ws: Path,
    revision: str,
) -> None:
    if not ws.is_file():
        return
    fm = parse_frontmatter(ws.read_text(encoding="utf-8"))
    state = fm.get("current_state", "")
    if state not in _FLAT_VALID_STATES:
        return
    sessions.append(
        SessionInfo(
            revision=revision,
            state=state,
            created_at=fm.get("updated_at", ""),
            state_path=ws,
        )
    )


def get_sessions(cycle_id: str, stage: str, cache_dir: Path) -> List[SessionInfo]:
    """Scan the stage directory and return SessionInfo list.

    For ``lulu-approach``, also scans nested ``main/session-state.md`` and
    ``D*/session-state.md`` under the stage dir (flat root kept for back-compat).
    """
    stage_dir = resolve_stage_cache_dir(cache_dir, cycle_id, stage)
    if not stage_dir.is_dir():
        return []
    sessions: List[SessionInfo] = []
    if stage in STAGE_FLAT:
        _append_flat_session(sessions, stage_dir / "session-state.md", "r0")
        if stage == "lulu-approach":
            _append_flat_session(
                sessions, stage_dir / "main" / "session-state.md", "main"
            )
            for child in sorted(stage_dir.iterdir()):
                if child.is_dir() and _APPROACH_DX_DIR_PAT.match(child.name):
                    _append_flat_session(
                        sessions, child / "session-state.md", child.name
                    )
    else:
        for rev_dir in sorted(stage_dir.iterdir()):
            if not _STAGE_REVISION_PAT.match(rev_dir.name):
                continue
            ws = rev_dir / "workflow-state.md"
            if not ws.exists():
                continue
            fm = parse_frontmatter(ws.read_text(encoding="utf-8"))
            state = fm.get("current_state", "")
            if state not in _VALID_STATES:
                continue
            sessions.append(SessionInfo(
                revision=rev_dir.name,
                state=state,
                created_at=fm.get("updated_at", ""),
                state_path=ws,
            ))
    return sessions


def has_any_valid_session(cycle_id: str, stage: str, cache_dir: Path) -> bool:
    """Return True if at least one session has state != Invalidated."""
    return any(s.state != "Invalidated" for s in get_sessions(cycle_id, stage, cache_dir))


def _approach_stage_delivered(cycle_id: str, cache_dir: Path) -> bool:
    """True when cycle delivered-refs records approach decision-package (stage Deliver)."""
    refs_path = cache_dir / cycle_id / "delivered-refs.json"
    if not refs_path.is_file():
        return False
    try:
        data = json.loads(refs_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(data, dict):
        return False
    entries = data.get("entries") or {}
    if not isinstance(entries, dict):
        return False
    entry = entries.get("lulu-approach")
    if not isinstance(entry, dict):
        return False
    artifact = str(entry.get("artifact") or "").strip()
    path = str(entry.get("path") or "")
    if artifact == "decision-package":
        return True
    return path.endswith("decision-package.json") or "/decision-package.json" in path


def current_effective_delivered(cycle_id: str, stage: str, cache_dir: Path) -> bool:
    """Return True if the stage is effectively delivered for transition gates.

    - ``lulu-approach``: cycle delivered-refs ``decision-package`` only.
    - ``decision`` / ``lulu-bet``: latest flat session is Completed (legacy Delivered OK).
    - Compose revisions: latest non-Invalidated workflow-state is Delivered.
    """
    if stage == "lulu-approach":
        return _approach_stage_delivered(cycle_id, cache_dir)

    valid = [s for s in get_sessions(cycle_id, stage, cache_dir) if s.state != "Invalidated"]
    if not valid:
        return False
    latest = max(valid, key=lambda s: (s.created_at, s.revision))
    if stage in {"decision", "lulu-bet"}:
        return latest.state in _FLAT_SESSION_TERMINAL
    return latest.state == "Delivered"
