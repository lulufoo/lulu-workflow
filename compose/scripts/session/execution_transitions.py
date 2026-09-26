#!/usr/bin/env python3
"""Pure step transitions over ``execution-state.json`` payloads.

Every function returns a new payload; callers persist it under the revision
lock. No filesystem access here.
"""

from __future__ import annotations

from typing import Any

_EVALUATING_PREVIOUS = frozenset({"Writing", "FreeEdit"})
_STEP_TABLE: dict[str, tuple[frozenset[str], str]] = {
    "enter-fact-intake": (frozenset({"Pending"}), "FactIntake"),
    "enter-inductive": (frozenset({"FactIntake"}), "Inductive"),
    "enter-deductive": (frozenset({"FactIntake", "Inductive"}), "Deductive"),
    "enter-writing": (frozenset({"Deductive"}), "Writing"),
    "enter-freeedit": (frozenset({"Writing"}), "FreeEdit"),
    "enter-evaluating": (_EVALUATING_PREVIOUS, "Evaluating"),
    "reverse-to-inductive": (frozenset({"FreeEdit"}), "Inductive"),
    "reverse-to-deductive": (frozenset({"FreeEdit"}), "Deductive"),
    "reverse-to-writing": (frozenset({"FreeEdit"}), "Writing"),
    "accept": (frozenset({"Evaluating"}), "Completed"),
    "fix": (frozenset({"Evaluating"}), "FreeEdit"),
    "reopen": (frozenset({"Completed"}), "FreeEdit"),
}
STEP_COMMANDS = frozenset(_STEP_TABLE)


class IllegalTransitionError(ValueError):
    """Raised when a step command is not legal from the current state."""

    def __init__(self, code: str, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.code = code
        self.extra = dict(extra)


def _next(state: dict[str, Any], target: str) -> dict[str, Any]:
    return {"version": state["version"], "state": target}


def apply_step(state: dict[str, Any], command: str) -> dict[str, Any]:
    """Return the payload after ``command``; raise when the source state is wrong."""
    if command not in _STEP_TABLE:
        raise IllegalTransitionError("unknown_command", f"unknown step command: {command!r}")
    allowed, target = _STEP_TABLE[command]
    current = str(state.get("state", ""))
    if current not in allowed:
        raise IllegalTransitionError(
            "illegal_transition",
            f"{command} requires {' or '.join(sorted(allowed))}, current is {current!r}",
            state=current,
        )
    return _next(state, target)


def abort_evaluating(state: dict[str, Any], *, previous: str) -> dict[str, Any]:
    """Restore the producer state a failed Eval admission started from."""
    current = str(state.get("state", ""))
    if current != "Evaluating":
        raise IllegalTransitionError(
            "illegal_transition", "abort-evaluating requires Evaluating", state=current
        )
    if previous not in _EVALUATING_PREVIOUS:
        raise IllegalTransitionError(
            "illegal_transition",
            "abort-evaluating previous must be Writing or FreeEdit",
        )
    return _next(state, previous)
