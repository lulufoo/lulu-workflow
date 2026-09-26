#!/usr/bin/env python3
"""Eval-facing entry points into the execution step machine.

Used by ``compose_eval_adapter`` / ``eval_handoff_control`` when Eval takes
over an execution in Writing or FreeEdit.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

import execution_checks as checks  # noqa: E402
from execution_context import ExecutionContext, require_working  # noqa: E402
from execution_state_schema import (  # noqa: E402
    execution_dir,
    load_execution_state,
    save_execution_state,
)
from execution_transitions import IllegalTransitionError, abort_evaluating  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID  # noqa: E402


def _refused(current: str, error: str) -> dict[str, Any]:
    return {
        "ok": False,
        "current_state": current,
        "transitioned": False,
        "error": error,
        "resume": {"entry": current, "action": error},
    }


def candidate_eval_round(execution_dir_path: Path) -> int:
    """Next evaluate round derived from ``execution/evaluate-state.md``."""
    es_path = Path(execution_dir_path) / "evaluate-state.md"
    if not es_path.is_file():
        return 1
    status, current = "", 1
    for line in es_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("eval_status:"):
            status = line.split(":", 1)[1].strip()
        elif line.startswith("evaluate_round:"):
            try:
                current = int(line.split(":", 1)[1].strip())
            except ValueError:
                current = 1
    return current + 1 if status in {"done", "abandoned"} else max(current, 1)


def enter_evaluating_state(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Ensure execution is Evaluating; session remains Working."""
    from execution_control import run_command  # noqa: WPS433

    ctx = ExecutionContext.build(cycle_id, project_root, profile_id)
    blocked = require_working("enter-evaluating", ctx)
    if blocked:
        return _refused(str(blocked.get("session_state") or ""), str(blocked["error"]))
    try:
        state = str(load_execution_state(ctx.revision_dir)["state"])
    except (OSError, ValueError) as exc:
        return _refused("Working", str(exc))
    transitioned = False
    if state != "Evaluating":
        result = run_command("enter-evaluating", cycle_id, project_root, profile_id=profile_id)
        if not result.get("ok"):
            error = str(result.get("error") or result.get("code") or "enter-evaluating failed")
            return _refused("Working", error)
        transitioned = True
    return {
        "ok": True,
        "current_state": "Working",
        "phase": "evaluating",
        "evaluate_round": candidate_eval_round(ctx.execution_dir),
        "transitioned": transitioned,
    }


def rollback_evaluating_phase(revision_dir: Path, *, previous_phase: str = "") -> None:
    """Restore Writing/FreeEdit after a failed first-enter Eval admission.

    ``previous_phase`` is provider-opaque; any other token leaves Evaluating
    and its eval run untouched.
    """
    if previous_phase not in {"Writing", "FreeEdit"}:
        return
    rev = Path(revision_dir).resolve()
    try:
        state = load_execution_state(rev)
        save_execution_state(rev, abort_evaluating(state, previous=previous_phase))
    except (IllegalTransitionError, OSError, ValueError):
        return
    checks.clear_eval_run(execution_dir(rev))
