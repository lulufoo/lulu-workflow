#!/usr/bin/env python3
"""Tests for l_transition_kernel (shell + step, no I/O)."""

from __future__ import annotations

import bootstrap  # noqa: F401
import pytest

from l_ledger_schema import build_ledger
from l_transition_kernel import (
    IllegalTransition,
    shell_advance,
    shell_backtrack,
    shell_unfreeze,
    step_abort_evaluating,
    step_accept,
    step_enter_evaluating,
    step_enter_deductive,
    step_enter_fact_intake,
    step_enter_freeedit,
    step_enter_inductive,
    step_enter_writing,
    step_fix,
    step_reopen,
    step_reverse_to_deductive,
    step_reverse_to_inductive,
    step_reverse_to_writing,
)


def _chain() -> dict:
    return build_ledger(["L1", "L2", "L3"])


def _produce(profile: dict, ledger: dict | None = None) -> dict:
    ledger = step_enter_fact_intake(ledger or _chain())
    if profile.get("inductive") is True:
        ledger = step_enter_inductive(ledger)
    return step_enter_deductive(ledger)


def _completed_prefix_writing() -> dict:
    ledger = _chain()
    ledger["by_id"]["L1"]["state"] = "Completed"
    ledger["focus"] = "L2"
    ledger["by_id"]["L2"]["state"] = "Writing"
    return ledger


def test_enter_fact_intake_from_pending() -> None:
    ledger = step_enter_fact_intake(_chain())
    assert ledger["by_id"]["L1"]["state"] == "FactIntake"


def test_enter_deductive_requires_fact_intake() -> None:
    with pytest.raises(IllegalTransition) as exc:
        step_enter_deductive(_chain())
    assert exc.value.code == "illegal_transition"


def test_enter_follows_serial_profile() -> None:
    inductive = step_enter_inductive(step_enter_fact_intake(_chain()))
    assert inductive["by_id"]["L1"]["state"] == "Inductive"
    serial = step_enter_deductive(inductive)
    assert serial["by_id"]["L1"]["state"] == "Deductive"
    projection = step_enter_deductive(step_enter_fact_intake(_chain()))
    assert projection["by_id"]["L1"]["state"] == "Deductive"


def test_enter_writing_rejects_inductive() -> None:
    ledger = step_enter_inductive(step_enter_fact_intake(_chain()))
    with pytest.raises(IllegalTransition):
        step_enter_writing(ledger)


def test_happy_path_to_completed() -> None:
    profile = {"inductive": False, "freeedit": True}
    ledger = _produce(profile)
    ledger = step_enter_writing(ledger)
    ledger = step_enter_freeedit(ledger, profile)
    ledger = step_enter_evaluating(ledger)
    ledger = step_accept(ledger)
    assert ledger["by_id"]["L1"]["state"] == "Completed"
    assert ledger["focus"] == "L1"


def test_abort_evaluating_restores_previous_phase() -> None:
    ledger = _produce({"inductive": False})
    ledger = step_enter_writing(ledger)
    ledger = step_enter_evaluating(ledger)
    restored = step_abort_evaluating(ledger, previous="Writing")
    assert restored["by_id"]["L1"]["state"] == "Writing"
    ledger = step_enter_evaluating(restored)
    with pytest.raises(IllegalTransition):
        step_abort_evaluating(ledger, previous="Evaluating")


def test_skip_freeedit_to_evaluating() -> None:
    ledger = _produce({"inductive": False})
    ledger = step_enter_writing(ledger)
    ledger = step_enter_evaluating(ledger)
    assert ledger["by_id"]["L1"]["state"] == "Evaluating"


def test_enter_freeedit_rejected_when_disabled() -> None:
    ledger = _produce({"inductive": False})
    ledger = step_enter_writing(ledger)
    with pytest.raises(IllegalTransition) as exc:
        step_enter_freeedit(ledger, {"freeedit": False})
    assert exc.value.code == "illegal_transition"


def test_writing_cannot_reverse_to_deductive() -> None:
    ledger = _produce({"inductive": True})
    ledger = step_enter_writing(ledger)
    with pytest.raises(IllegalTransition):
        step_reverse_to_deductive(ledger)


def test_freeedit_reverse_and_fix_reopen() -> None:
    profile = {"inductive": True, "freeedit": True}
    ledger = _produce(profile)
    ledger = step_enter_writing(ledger)
    ledger = step_enter_freeedit(ledger, profile)
    ledger = step_reverse_to_inductive(ledger)
    assert ledger["by_id"]["L1"]["state"] == "Inductive"
    ledger = step_enter_deductive(ledger)
    ledger = step_enter_writing(ledger)
    ledger = step_enter_freeedit(ledger, profile)
    ledger = step_reverse_to_writing(ledger)
    assert ledger["by_id"]["L1"]["state"] == "Writing"
    ledger = step_enter_evaluating(ledger)
    ledger = step_fix(ledger)
    assert ledger["by_id"]["L1"]["state"] == "FreeEdit"
    ledger = step_enter_evaluating(ledger)
    ledger = step_accept(ledger)
    ledger = step_reopen(ledger)
    assert ledger["by_id"]["L1"]["state"] == "FreeEdit"


def test_advance_and_backtrack_and_unfreeze() -> None:
    profile = {"inductive": False, "freeedit": True}
    ledger = _chain()
    ledger = _produce(profile, ledger)
    ledger = step_enter_writing(ledger)
    ledger = step_enter_evaluating(ledger)
    ledger = step_accept(ledger)
    advanced = shell_advance(ledger)
    assert advanced.changed is True
    ledger = advanced.ledger
    assert ledger["focus"] == "L2"
    ledger = shell_backtrack(ledger, "L1")
    assert ledger["focus"] == "L1"
    assert ledger["by_id"]["L1"]["state"] == "FreeEdit"
    assert ledger["by_id"]["L2"]["frozen"] is True
    ledger = step_enter_evaluating(ledger)
    ledger = step_accept(ledger)
    with pytest.raises(IllegalTransition) as exc:
        shell_advance(ledger)
    assert exc.value.code == "alignment_required"
    ledger = shell_unfreeze(ledger)
    assert ledger["focus"] == "L2"
    assert ledger["by_id"]["L2"]["frozen"] is False
    assert ledger["by_id"]["L2"]["state"] == "Pending"


def test_advance_last_reports_ready() -> None:
    ledger = build_ledger(["L1"])
    ledger["by_id"]["L1"]["state"] = "Completed"
    result = shell_advance(ledger)
    assert result.changed is False
    assert result.next_action == "ready-for-delivery"


def test_nested_backtrack_keeps_frozen_suffix() -> None:
    ledger = _chain()
    ledger["by_id"]["L1"]["state"] = "Completed"
    ledger["by_id"]["L2"]["state"] = "Completed"
    ledger["focus"] = "L3"
    ledger["by_id"]["L3"]["state"] = "Writing"
    ledger = shell_backtrack(ledger, "L2")
    assert ledger["by_id"]["L3"]["frozen"] is True
    ledger["by_id"]["L2"]["state"] = "Completed"
    # after backtrack focus is L2 FreeEdit; accept path: evaluating then completed
    ledger["by_id"]["L2"]["state"] = "Completed"
    ledger = shell_backtrack(ledger, "L1")
    assert ledger["focus"] == "L1"
    assert ledger["by_id"]["L2"]["frozen"] is True
    assert ledger["by_id"]["L3"]["frozen"] is True


def test_backtrack_rejects_non_predecessor() -> None:
    ledger = _completed_prefix_writing()
    with pytest.raises(IllegalTransition):
        shell_backtrack(ledger, "L2")
    with pytest.raises(IllegalTransition):
        shell_backtrack(ledger, "L3")
