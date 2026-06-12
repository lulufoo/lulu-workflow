#!/usr/bin/env python3
"""Eval control for tech-plan orchestrator.

Owns mechanical writes to evaluate-state.md. workflow-state transitions stay in
session_control.py.

Implemented subcommands (internal / future CLI):
    init-round            Initialize evaluate-state.md for a new evaluation round

Reserved (not yet implemented):
    validate-entry        Confirm evaluate-state matches workflow mode (E1)
    begin-dimension       Set current_dimension and in_progress status (E3)
    check-dimension       Read dimension completion / abandoned status (E3)
    set-total-issues      Write per-dimension issue count (eval-runner)
    abandon               Set current_dimension: abandoned (eval-runner)
    complete-dimension    Finalize a dimension (eval-runner)
    finalize-round        Set done + fix_severity after all dimensions (E4)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_state_schema import (  # noqa: E402
    init_evaluate_state,
    resolve_evaluate_state_path_from_cycle,
)

_CMD_INIT_ROUND = "init-round"

_VALID_MODES = frozenset({"product", "tech"})
_VALID_DIMS = frozenset({"e1", "e2", "e3"})
_DISPATCH_BY_MODE = {"product": ["e1", "e2", "e3"], "tech": ["e2", "e3"]}
_SEVERITY_RANK = {"critical": 3, "medium": 2, "minor": 1}


def dispatch_list(mode: str) -> list[str]:
    """Return eval dimension dispatch sequence for workflow mode (SSOT)."""
    if mode not in _VALID_MODES:
        raise ValueError(
            f"invalid mode: {mode!r} (allowed: {sorted(_VALID_MODES)})"
        )
    return list(_DISPATCH_BY_MODE[mode])


def _success(command: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "command": command}
    payload.update(extra)
    return payload


def init_round(
    cycle_id: str,
    project_root: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    """Initialize evaluate-state.md for the current active revision.

    Caller must ensure workflow-state is already Evaluating. Does not read or
    write workflow-state.md. Not idempotent — session_control skips re-entry.
    """
    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    init_evaluate_state(es_path, mode=mode)
    return _success(
        _CMD_INIT_ROUND,
        mode=mode,
        path=es_path.resolve().as_posix(),
    )
