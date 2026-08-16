#!/usr/bin/env python3
"""Pure L-ledger transitions and global invariant checks.

Control layers call these functions, then validate + atomic-save via
``l_ledger_schema``. This module does not read or write files.

Design rationale:
docs/domain/archive/compose/archive-33.0/compose-outer-shell-management-subdesign.md
docs/domain/archive/compose/archive-33.0/compose-l-execution-subdesign.md
"""

from __future__ import annotations

import copy
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent.parent
_SCHEMA_SESSION = _SCRIPTS / "schema" / "session"
if str(_SCHEMA_SESSION) not in sys.path:
    sys.path.insert(0, str(_SCHEMA_SESSION))

from l_ledger_schema import (
    all_completed_unfrozen,
    focus_index,
    reached_frontier,
    validate_l_ledger,
)

PRODUCER_STATES = frozenset({"Inductive", "Deductive"})


class IllegalTransition(ValueError):
    """A ledger command that must not write."""

    def __init__(self, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.extra = extra


@dataclass(frozen=True)
class ShellAdvance:
    ledger: dict[str, Any]
    changed: bool
    next_action: str | None = None


def validate_global_invariants(ledger: dict[str, Any]) -> list[str]:
    return validate_l_ledger(ledger)


def _clone(ledger: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(ledger)


def _cell(ledger: dict[str, Any], nid: str) -> dict[str, Any]:
    return ledger["by_id"][nid]


def _require_unfrozen_focus(ledger: dict[str, Any]) -> str:
    focus = str(ledger["focus"])
    if _cell(ledger, focus)["frozen"] is True:
        raise IllegalTransition(
            "illegal_transition",
            f"focus {focus} is frozen",
        )
    return focus


def _finish(ledger: dict[str, Any]) -> dict[str, Any]:
    errors = validate_l_ledger(ledger)
    if errors:
        raise IllegalTransition("invalid_ledger", "; ".join(errors))
    return ledger


# --- $L_SHELL ---


def shell_advance(ledger: dict[str, Any]) -> ShellAdvance:
    """Advance focus to the direct successor, or signal ready/align."""
    focus = _require_unfrozen_focus(ledger)
    if _cell(ledger, focus)["state"] != "Completed":
        raise IllegalTransition(
            "illegal_transition",
            f"advance requires focus {focus} Completed",
        )
    order = list(ledger["order"])
    f = focus_index(ledger)
    if f + 1 >= len(order):
        if not all_completed_unfrozen(ledger):
            raise IllegalTransition(
                "illegal_transition",
                "last L is Completed but ledger is not ready-for-delivery",
            )
        return ShellAdvance(
            ledger=_clone(ledger),
            changed=False,
            next_action="ready-for-delivery",
        )
    nxt = order[f + 1]
    if _cell(ledger, nxt)["frozen"] is True:
        raise IllegalTransition(
            "alignment_required",
            f"successor {nxt} is frozen",
            successor=nxt,
        )
    new = _clone(ledger)
    new["focus"] = nxt
    return ShellAdvance(ledger=_finish(new), changed=True)


def shell_backtrack(ledger: dict[str, Any], target: str) -> dict[str, Any]:
    order = list(ledger["order"])
    if target not in order:
        raise IllegalTransition("illegal_transition", f"unknown target {target}")
    f = focus_index(ledger)
    t = order.index(target)
    if t >= f:
        raise IllegalTransition(
            "illegal_transition",
            "backtrack target must be a strict predecessor",
        )
    cell = _cell(ledger, target)
    if cell["state"] != "Completed" or cell["frozen"] is True:
        raise IllegalTransition(
            "illegal_transition",
            "backtrack target must be Completed and unfrozen",
        )
    r = reached_frontier(ledger)
    new = _clone(ledger)
    new["focus"] = target
    new["by_id"][target]["state"] = "FreeEdit"
    new["by_id"][target]["frozen"] = False
    for i in range(t + 1, r + 1):
        nid = order[i]
        new["by_id"][nid]["frozen"] = True
    return _finish(new)


def shell_unfreeze(ledger: dict[str, Any]) -> dict[str, Any]:
    focus = _require_unfrozen_focus(ledger)
    if _cell(ledger, focus)["state"] != "Completed":
        raise IllegalTransition(
            "illegal_transition",
            f"unfreeze requires focus {focus} Completed",
        )
    order = list(ledger["order"])
    f = focus_index(ledger)
    if f + 1 >= len(order):
        raise IllegalTransition(
            "illegal_transition",
            "unfreeze requires a frozen direct successor",
        )
    nxt = order[f + 1]
    if _cell(ledger, nxt)["frozen"] is not True:
        raise IllegalTransition(
            "illegal_transition",
            f"direct successor {nxt} is not frozen",
        )
    prefix_ok = all(
        _cell(ledger, nid)["state"] == "Completed"
        and _cell(ledger, nid)["frozen"] is False
        for nid in order[: f + 1]
    )
    if not prefix_ok:
        raise IllegalTransition(
            "illegal_transition",
            "unfreeze requires Completed unfrozen prefix through focus",
        )
    new = _clone(ledger)
    new["by_id"][nxt]["frozen"] = False
    new["focus"] = nxt
    return _finish(new)


# --- $L_STEP ---


def _producer_state(profile: dict[str, Any]) -> str:
    if profile.get("inductive") is True:
        return "Inductive"
    return "Deductive"


def step_enter_producer(
    ledger: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    focus = _require_unfrozen_focus(ledger)
    if _cell(ledger, focus)["state"] != "Pending":
        raise IllegalTransition(
            "illegal_transition",
            "enter-producer requires Pending focus",
        )
    new = _clone(ledger)
    new["by_id"][focus]["state"] = _producer_state(profile)
    return _finish(new)


def step_enter_writing(ledger: dict[str, Any]) -> dict[str, Any]:
    focus = _require_unfrozen_focus(ledger)
    if _cell(ledger, focus)["state"] not in PRODUCER_STATES:
        raise IllegalTransition(
            "illegal_transition",
            "enter-writing requires Inductive or Deductive focus",
        )
    new = _clone(ledger)
    new["by_id"][focus]["state"] = "Writing"
    return _finish(new)


def step_enter_freeedit(
    ledger: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    if profile.get("freeedit") is not True:
        raise IllegalTransition(
            "illegal_transition",
            "enter-freeedit requires pipeline.freeedit",
        )
    focus = _require_unfrozen_focus(ledger)
    if _cell(ledger, focus)["state"] != "Writing":
        raise IllegalTransition(
            "illegal_transition",
            "enter-freeedit requires Writing focus",
        )
    new = _clone(ledger)
    new["by_id"][focus]["state"] = "FreeEdit"
    return _finish(new)


def step_enter_evaluating(ledger: dict[str, Any]) -> dict[str, Any]:
    focus = _require_unfrozen_focus(ledger)
    if _cell(ledger, focus)["state"] not in {"Writing", "FreeEdit"}:
        raise IllegalTransition(
            "illegal_transition",
            "enter-evaluating requires Writing or FreeEdit",
        )
    new = _clone(ledger)
    new["by_id"][focus]["state"] = "Evaluating"
    return _finish(new)


def step_reverse_to_producer(
    ledger: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    focus = _require_unfrozen_focus(ledger)
    if _cell(ledger, focus)["state"] != "FreeEdit":
        raise IllegalTransition(
            "illegal_transition",
            "reverse-to-producer requires FreeEdit",
        )
    new = _clone(ledger)
    new["by_id"][focus]["state"] = _producer_state(profile)
    return _finish(new)


def step_reverse_to_writing(ledger: dict[str, Any]) -> dict[str, Any]:
    focus = _require_unfrozen_focus(ledger)
    if _cell(ledger, focus)["state"] != "FreeEdit":
        raise IllegalTransition(
            "illegal_transition",
            "reverse-to-writing requires FreeEdit",
        )
    new = _clone(ledger)
    new["by_id"][focus]["state"] = "Writing"
    return _finish(new)


def step_accept(ledger: dict[str, Any]) -> dict[str, Any]:
    focus = _require_unfrozen_focus(ledger)
    if _cell(ledger, focus)["state"] != "Evaluating":
        raise IllegalTransition(
            "illegal_transition",
            "accept requires Evaluating",
        )
    new = _clone(ledger)
    new["by_id"][focus]["state"] = "Completed"
    return _finish(new)


def step_fix(ledger: dict[str, Any]) -> dict[str, Any]:
    focus = _require_unfrozen_focus(ledger)
    if _cell(ledger, focus)["state"] != "Evaluating":
        raise IllegalTransition("illegal_transition", "fix requires Evaluating")
    new = _clone(ledger)
    new["by_id"][focus]["state"] = "FreeEdit"
    return _finish(new)


def step_abort_evaluating(ledger: dict[str, Any], *, previous: str) -> dict[str, Any]:
    focus = _require_unfrozen_focus(ledger)
    if _cell(ledger, focus)["state"] != "Evaluating":
        raise IllegalTransition(
            "illegal_transition",
            "abort-evaluating requires Evaluating",
        )
    if previous not in {"Writing", "FreeEdit"}:
        raise IllegalTransition(
            "illegal_transition",
            "abort-evaluating previous must be Writing or FreeEdit",
        )
    new = _clone(ledger)
    new["by_id"][focus]["state"] = previous
    return _finish(new)


def step_reopen(ledger: dict[str, Any]) -> dict[str, Any]:
    focus = _require_unfrozen_focus(ledger)
    if _cell(ledger, focus)["state"] != "Completed":
        raise IllegalTransition(
            "illegal_transition",
            "reopen requires Completed focus",
        )
    new = _clone(ledger)
    new["by_id"][focus]["state"] = "FreeEdit"
    return _finish(new)
