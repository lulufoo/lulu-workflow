#!/usr/bin/env python3
"""After-DC next-step messaging from config/transition-table.json."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from transition_table import load_transitions  # noqa: E402


def next_steps_for_stage(stage: str, cycle_type: str) -> list[str]:
    """Return sorted next stage ids from transition-table for (cycle_type, stage)."""
    transitions = load_transitions(cycle_type)
    return sorted(transitions.get(stage, set()))


def build_after_dc(stage: str, cycle_type: str) -> dict[str, Any]:
    """Build after_dc payload for resolve-context (raw stage ids only)."""
    steps = next_steps_for_stage(stage, cycle_type)
    if steps:
        joined = ", ".join(steps)
        message = f"{stage} is complete. The next step is: {joined}."
    else:
        message = f"{stage} is complete."
    return {
        "next_steps": steps,
        "user_message": message,
    }
