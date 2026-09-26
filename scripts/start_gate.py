"""Start gate validation and topic document resolution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple, TypedDict

from cycle_schema import read_stage as read_cycle_state
from transition_table import known_stages, load_transitions
from workflow_sessions import current_effective_delivered
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


class TopicRef(TypedDict):
    """Topic-line delivered ref: {type, path}, mirroring DeliveredRef.to_dict()."""

    type: str
    path: str


def get_topic_ref(cycle_id: str, stage: str, cache_dir: Path) -> Optional[TopicRef]:
    """Return the topic's delivered ref for the stage referenced by a feature, or None.

    Resolved entirely from generic cache artifacts (``cycles.json``,
    ``transition-table.json``, the topic's own ``delivered-refs.json``) — never
    from a stage's own ``scripts/`` — so this stays valid across decision and
    compose kernels alike (see .cursor/skills/lulu-discipline-skills/skill/skill-architecture-constraints.md
    § lulu-workflow Module Dependencies).
    """
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

    topic_refs_path = cache_dir / topic_id / "delivered-refs.json"
    if not topic_refs_path.exists():
        return None
    topic_refs = json.loads(topic_refs_path.read_text(encoding="utf-8"))
    entry = (topic_refs.get("entries") or {}).get(ref_stage)
    if not isinstance(entry, dict):
        return None
    raw_path = str(entry.get("path", "")).strip()
    if not raw_path or not Path(raw_path).is_file():
        return None
    return {"type": ref_stage, "path": raw_path}


def get_topic_doc(cycle_id: str, stage: str, cache_dir: Path) -> Optional[Path]:
    """Return the topic's latest delivered doc path for a feature's stage, or None."""
    ref = get_topic_ref(cycle_id, stage, cache_dir)
    return Path(ref["path"]) if ref is not None else None


__all__ = ["check_gate", "get_topic_doc", "get_topic_ref", "TopicRef"]
