#!/usr/bin/env python3
"""Cycle stage transitions from config/transition-table.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "transition-table.json"

LEGACY_STAGES = frozenset({"decision"})


def load_transitions(cycle_type: str) -> dict:
    """Load transition-table.json → {from_stage|None: set(to_stages)}."""
    tt = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    result: dict = {}
    for entry in tt.get(cycle_type, []):
        result.setdefault(entry.get("from"), set()).update(entry.get("to", []))
    return result


def known_stages(cycle_type: str) -> frozenset[str]:
    """All cycle stages = non-null from keys in transition-table.json."""
    return frozenset(k for k in load_transitions(cycle_type) if k is not None)


def allowed_stages(cycle_type: str) -> frozenset[str]:
    """Stages valid for active-context, including legacy entries."""
    return known_stages(cycle_type) | LEGACY_STAGES


def load_stage_order(cycle_type: str) -> List[str]:
    """Derive ordered stage list from non-null transitions in transition-table.json."""
    transitions = load_transitions(cycle_type)
    forward = {k: sorted(v)[0] for k, v in transitions.items() if k is not None and v}
    all_targets = set(forward.values())
    roots = [s for s in forward if s not in all_targets]
    order: List[str] = []
    current: Optional[str] = roots[0] if roots else None
    while current:
        order.append(current)
        current = forward.get(current)
    return order


def topic_doc_stage_for(stage: str) -> Optional[str]:
    """Return topic-line doc stage for a feature-line stage, or None if not mapped."""
    tt = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    return tt.get("topic_doc_stage", {}).get(stage)
