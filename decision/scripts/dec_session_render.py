#!/usr/bin/env python3
"""Session render helpers for diagnostic (legacy reply_header stub)."""

from __future__ import annotations

from typing import Any


def render_reply_header(gate_state: dict[str, Any], registers: dict[str, Any]) -> str:
    """Reply Header is not shown to users; gate/register SSOT lives on disk."""
    del gate_state, registers
    return ""
