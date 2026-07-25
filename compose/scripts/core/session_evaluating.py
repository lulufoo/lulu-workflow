"""Compose workflow-state transition into Evaluating (no eval kernel calls)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_CORE = Path(__file__).resolve().parent
_SCRIPTS = _CORE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_session import workflow_state_path  # noqa: E402
from discussion_pointer_control import stage_gate_for_revision  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID  # noqa: E402
from workflow_state_schema import load_workflow_state, save_workflow_state  # noqa: E402


def enter_evaluating_state(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Move workflow-state Drafting → Evaluating. Does not touch evaluate-state.md.

    Multi-L StageGate (v1.1): when ``discussion-pointer.json`` exists, every
    dependency of the current focus must have ``production: done``.
    """
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current == "Evaluating":
        try:
            evaluate_round = int(state.get("evaluate_round", "0"))
        except ValueError:
            evaluate_round = 0
        return {
            "ok": True,
            "current_state": "Evaluating",
            "evaluate_round": evaluate_round,
            "transitioned": False,
        }

    if current != "Drafting":
        return {
            "ok": False,
            "current_state": current,
            "transitioned": False,
            "resume": {
                "entry": current,
                "action": f"当前状态是 {current}，请先执行完 {current}。",
            },
        }

    revision_dir = ws_path.parent
    gate_ok, gate_reason = stage_gate_for_revision(revision_dir)
    if not gate_ok:
        return {
            "ok": False,
            "current_state": current,
            "transitioned": False,
            "error": gate_reason or "StageGate blocked Evaluating entry",
            "resume": {
                "entry": current,
                "action": (
                    "StageGate: 前置 L 尚未 production=done，不能进入 Evaluating。"
                    f" ({gate_reason})"
                ),
            },
        }

    try:
        evaluate_round = int(state.get("evaluate_round", "0")) + 1
    except ValueError:
        evaluate_round = 1

    merged = dict(state)
    merged.pop("skip_evaluate_requested", None)
    merged["current_state"] = "Evaluating"
    merged["evaluate_round"] = str(evaluate_round)
    save_workflow_state(ws_path, merged, merge=False)

    return {
        "ok": True,
        "current_state": "Evaluating",
        "evaluate_round": evaluate_round,
        "transitioned": True,
    }


def transition_to_evaluating(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Deprecated alias for enter_evaluating_state (evaluate init moved to eval adapter)."""
    return enter_evaluating_state(cycle_id, project_root, profile_id=profile_id)
