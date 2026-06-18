"""Shared agent STOP messaging for workflow enforcement."""

from __future__ import annotations


def agent_stop_message(
    detail: str,
    *,
    forbidden: str,
    workarounds: str,
) -> str:
    return (
        f"{detail}\n"
        f"STOP: Do not retry {forbidden} or attempt workarounds "
        f"({workarounds}).\n"
        "Report this message to the user and wait for their direction."
    )
