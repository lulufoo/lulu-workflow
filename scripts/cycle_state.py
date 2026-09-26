#!/usr/bin/env python3
"""Per-cycle current-stage tracking via cycle-state.json.

Deprecated import path — use cycle_schema.read_stage / write_stage.
"""

from __future__ import annotations

from pathlib import Path

from cycle_schema import read_stage as read_cycle_state  # noqa: F401
from cycle_schema import write_stage as write_cycle_state  # noqa: F401

__all__ = ["read_cycle_state", "write_cycle_state"]
