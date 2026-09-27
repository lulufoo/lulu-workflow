#!/usr/bin/env python3
"""Read and write lulu-tasks session-state.md."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tt_workflow_common import parse_frontmatter_fields, session_state_path


def session_file(project_root: Path, cycle_id: str) -> Path:
    return project_root / session_state_path(cycle_id)


def read_active_doc(path: Path) -> int:
    if not path.is_file():
        return 0
    raw = parse_frontmatter_fields(path.read_text(encoding="utf-8")).get("active_doc", "0")
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"active_doc is not an integer: {raw!r}") from exc


def write_session_state(path: Path, active_doc: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    path.write_text(
        f"---\nversion: 1\nactive_doc: {int(active_doc)}\nupdated_at: {now}\n---\n",
        encoding="utf-8",
    )
