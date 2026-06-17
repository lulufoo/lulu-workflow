"""Invalidation hook: cascades Invalidated state to downstream sessions."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hook_guard import get_sessions, load_stage_order  # noqa: E402

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_KERNEL_CORE = _SKILL_ROOT / "compose-kernel" / "scripts" / "core"
_KERNEL_SCHEMA_SESSION = _SKILL_ROOT / "compose-kernel" / "scripts" / "schema" / "session"


def _is_tech_plan_workflow_state(state_path: Path) -> bool:
    parts = state_path.parts
    if state_path.name != "workflow-state.md":
        return False
    if "tech" not in parts or "plan" not in parts:
        return False
    return any(part.startswith("revision") for part in parts)


def _write_invalidated_regex(state_path: Path) -> None:
    """Set current_state to Invalidated in workflow-state.md, preserving all other fields."""
    text = state_path.read_text(encoding="utf-8")
    updated = re.sub(
        r"(?m)^(current_state:\s*).*$",
        r"\g<1>Invalidated",
        text,
    )
    state_path.write_text(updated, encoding="utf-8")


def _write_invalidated(state_path: Path) -> None:
    if _is_tech_plan_workflow_state(state_path):
        for scripts_dir in (_KERNEL_CORE, _KERNEL_SCHEMA_SESSION):
            s = str(scripts_dir)
            if s not in sys.path:
                sys.path.insert(0, s)
        try:
            from workflow_state_schema import mark_invalidated  # noqa: WPS433

            mark_invalidated(state_path)
            return
        except ValueError:
            pass
    _write_invalidated_regex(state_path)


def invalidate_downstream(cycle_id: str, from_stage: str,
                           cycle_type: str, cache_dir: Path) -> None:
    """Mark all non-Invalidated sessions in stages after from_stage as Invalidated."""
    stages = load_stage_order(cycle_type)
    if from_stage not in stages:
        return
    downstream = stages[stages.index(from_stage) + 1:]
    for stage in downstream:
        for session in get_sessions(cycle_id, stage, cache_dir):
            if session.state != "Invalidated":
                if session.state_path and session.state_path.exists():
                    _write_invalidated(session.state_path)
