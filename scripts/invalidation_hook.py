"""Invalidation hook: cascades Invalidated state to downstream sessions."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hook_guard import get_sessions, load_stage_order  # noqa: E402

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_DIR = _SKILL_ROOT / "config"


def _write_invalidated(state_path: Path) -> None:
    """Set current_state to Invalidated in workflow-state.md, preserving all other fields."""
    text = state_path.read_text(encoding="utf-8")
    updated = re.sub(
        r"(?m)^(current_state:\s*).*$",
        r"\g<1>Invalidated",
        text,
    )
    state_path.write_text(updated, encoding="utf-8")


def invalidate_downstream(cycle_id: str, from_stage: str,
                           cycle_type: str, cache_dir: Path) -> None:
    """Mark all non-Invalidated sessions in stages after from_stage as Invalidated."""
    stages = load_stage_order(cycle_type, _CONFIG_DIR)
    if from_stage not in stages:
        return
    downstream = stages[stages.index(from_stage) + 1:]
    for stage in downstream:
        for session in get_sessions(cycle_id, stage, cache_dir):
            if session.state != "Invalidated":
                if session.state_path and session.state_path.exists():
                    _write_invalidated(session.state_path)
