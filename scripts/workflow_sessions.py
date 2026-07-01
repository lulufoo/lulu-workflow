"""Session scanning and Delivered state for lulu-dev-workflow cache layouts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_VALID_STATES = frozenset({"Drafting", "Evaluating", "TDABlocked", "Delivered", "Invalidated"})

STAGE_FLAT = frozenset({"decision", "lulu-bet", "lulu-approach"})
_FLAT_VALID_STATES = frozenset({"InProgress", "Delivered", "Invalidated"})
_STAGE_REVISION_PAT = re.compile(r"^(revision|r|s)\d+$")

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


def get_sessions(cycle_id: str, stage: str, cache_dir: Path) -> List[SessionInfo]:
    """Scan the stage directory and return SessionInfo list."""
    stage_dir = cache_dir / cycle_id / stage_subdir(stage)
    if not stage_dir.is_dir():
        return []
    sessions = []
    if stage in STAGE_FLAT:
        ws = stage_dir / "session-state.md"
        if ws.exists():
            fm = parse_frontmatter(ws.read_text(encoding="utf-8"))
            state = fm.get("current_state", "")
            if state in _FLAT_VALID_STATES:
                sessions.append(SessionInfo(
                    revision="r0",
                    state=state,
                    created_at=fm.get("updated_at", ""),
                    state_path=ws,
                ))
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


def current_effective_delivered(cycle_id: str, stage: str, cache_dir: Path) -> bool:
    """Return True if the latest non-Invalidated session has state == Delivered."""
    valid = [s for s in get_sessions(cycle_id, stage, cache_dir) if s.state != "Invalidated"]
    if not valid:
        return False
    latest = max(valid, key=lambda s: (s.created_at, s.revision))
    return latest.state == "Delivered"
