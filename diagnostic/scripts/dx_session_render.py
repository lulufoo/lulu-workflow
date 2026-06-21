#!/usr/bin/env python3
"""Shared Reply Header rendering for diagnostic sessions."""

from __future__ import annotations

from typing import Any

from dx_gate_state_schema import header_gate_symbols
from dx_register_schema import format_assumption_header_line, format_prior_header_line


def render_reply_header(gate_state: dict[str, Any], registers: dict[str, Any]) -> str:
    """Return Reply Header text, or empty string when no register entries exist."""
    prior = registers.get("prior", [])
    assumptions = registers.get("assumptions", [])
    if not prior and not assumptions:
        return ""

    symbols = header_gate_symbols(gate_state)
    gate_line = (
        f"Gate: Q{symbols['Q']} E{symbols['E']} D{symbols['D']} X{symbols['X']} "
        f"R{symbols['R']} V{symbols['V']} RR{symbols['RR']} DC{symbols['DC']}"
    )
    lines = ["─── DDF ───────────────────────────────────────", gate_line]
    if prior:
        lines.append("Prior：")
        for entry in prior:
            if isinstance(entry, dict):
                lines.append(format_prior_header_line(entry))
    if assumptions:
        lines.append("Assumption：")
        for entry in assumptions:
            if isinstance(entry, dict):
                lines.append(format_assumption_header_line(entry))
    lines.append("───────────────────────────────────────────────")
    return "\n".join(lines)
