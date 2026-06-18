"""Start gate validation and topic document resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

from cycle_schema import read_stage as read_cycle_state
from transition_table import known_stages, load_transitions
from workflow_sessions import current_effective_delivered, get_sessions
from workflow_stop import agent_stop_message

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_DIR = _SKILL_ROOT / "config"


def check_gate(
    cycle_id: str,
    to_stage: str,
    cycle_type: str,
    cache_dir: Path,
) -> Tuple[bool, str]:
    """Validate gate for to_stage using transition-table.json rules."""
    transitions = load_transitions(cycle_type)
    all_stages = known_stages(cycle_type)
    if to_stage not in all_stages:
        return (True, "OK")

    current_stage = read_cycle_state(cycle_id, cache_dir)
    if current_stage is not None and current_stage not in all_stages:
        current_stage = None

    allowed = transitions.get(current_stage, set())
    is_reentry = (to_stage == current_stage)
    is_advance = (to_stage in allowed)

    if not is_reentry and not is_advance:
        expected = ", ".join(sorted(allowed)) or "terminal"
        return (
            False,
            agent_stop_message(
                f"Invalid transition: {current_stage or 'NULL'} → {to_stage} "
                f"(allowed: {expected})",
                forbidden="start.py",
                workarounds="alternate cycle, rollback, flags, etc.",
            ),
        )

    if is_advance and current_stage is not None:
        if not current_effective_delivered(cycle_id, current_stage, cache_dir):
            return (
                False,
                agent_stop_message(
                    f"{current_stage} is not Delivered",
                    forbidden="start.py",
                    workarounds="alternate cycle, rollback, flags, etc.",
                ),
            )

    return (True, "OK")


def get_topic_doc(cycle_id: str, stage: str, cache_dir: Path) -> Optional[Path]:
    """Return latest Delivered doc path for the topic referenced by a feature, or None."""
    cycles_path = cache_dir / "cycles.json"
    if not cycles_path.exists():
        return None
    cycles_data = json.loads(cycles_path.read_text(encoding="utf-8"))
    meta = cycles_data.get(cycle_id, {})
    if not isinstance(meta, dict):
        return None
    topic_id = meta.get("topic_id")
    if not topic_id:
        return None

    if topic_id not in cycles_data:
        raise ValueError(f"topic_id {topic_id!r} not found in cycles.json")

    transition_table = json.loads(
        (_CONFIG_DIR / "transition-table.json").read_text(encoding="utf-8")
    )
    ref_stage = transition_table.get("topic_doc_stage", {}).get(stage)
    if ref_stage is None:
        return None

    sessions = [
        session
        for session in get_sessions(topic_id, ref_stage, cache_dir)
        if session.state == "Delivered"
    ]
    if not sessions:
        return None
    latest = max(sessions, key=lambda s: (s.created_at, s.revision))
    doc_path = latest.state_path.parent if latest.state_path else None
    return doc_path if doc_path and doc_path.exists() else None


__all__ = ["check_gate", "get_topic_doc"]
