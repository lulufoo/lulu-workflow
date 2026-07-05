#!/usr/bin/env python3
"""Shared subagent dispatch guard for inductive artifact record commands."""

from __future__ import annotations

from pathlib import Path

from active_context_schema import resolve_conversation_id
from inductive_gate_state_schema import load_gate_state
from platform_schema import detect_platform

SUBAGENT_REQUIRED_PREFIX = "SUBAGENT_REQUIRED:"
MASTER_CONVERSATION_REQUIRED_PREFIX = "MASTER_CONVERSATION_REQUIRED:"
CONVERSATION_ID_REQUIRED_PREFIX = "CONVERSATION_ID_REQUIRED:"


def load_master_conversation_id(out_dir: Path) -> str:
    gate_path = out_dir / "inductive-gate-state.json"
    if not gate_path.exists():
        return ""
    try:
        state = load_gate_state(gate_path)
    except (FileNotFoundError, ValueError):
        return ""
    return str(state.get("master_conversation_id", "")).strip()


def require_subagent_dispatch(
    out_dir: Path,
    conversation_id: str,
    *,
    record_command: str,
    runner_skill: str,
    operation_label: str,
) -> None:
    """Reject record commands invoked from the orchestrating parent on Cursor."""
    if detect_platform() != "cursor":
        return

    master = load_master_conversation_id(out_dir)
    if not master:
        raise ValueError(
            f"{MASTER_CONVERSATION_REQUIRED_PREFIX} init-session must complete "
            f"before {record_command}. Re-run $INDUCTIVE_GATE_CTL init-session, "
            f"then dispatch {runner_skill}."
        )

    conv_id = resolve_conversation_id(conversation_id)
    if not conv_id:
        raise ValueError(
            f"{CONVERSATION_ID_REQUIRED_PREFIX} {record_command} failed: "
            "caller session identity missing; retry via dispatched subagent."
        )

    if master == conv_id:
        raise ValueError(
            f"{SUBAGENT_REQUIRED_PREFIX} {operation_label} must run in a dispatched "
            f"{runner_skill} subagent via $SUBAGENT_TOOL "
            "(run_in_background: false). Do not record inline from the "
            "orchestrating conversation. Dispatch the subagent and retry."
        )
