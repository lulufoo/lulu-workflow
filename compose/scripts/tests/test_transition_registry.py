#!/usr/bin/env python3
"""Tests for transition_registry.py."""

from __future__ import annotations

import bootstrap  # noqa: F401
from transition_registry import is_allowed, load_transition_table, session_states


def test_load_transition_table():
    data = load_transition_table()
    assert "states" in data
    assert "transitions" in data
    assert len(data["transitions"]) == 3


def test_session_states_match_whitelist():
    states = session_states()
    assert states == frozenset(
        {
            "Split",
            "Working",
            "ReadyForDelivery",
            "Delivered",
            "Invalidated",
        }
    )


def test_allowed_transitions():
    assert is_allowed("split-complete", "Split", "Working")
    assert is_allowed("ready-for-delivery", "Working", "ReadyForDelivery")
    assert is_allowed("deliver", "ReadyForDelivery", "Delivered")


def test_disallowed_transitions():
    assert not is_allowed("deliver", "Working", "Delivered")
    assert not is_allowed("ready-for-delivery", "Split", "ReadyForDelivery")
    assert not is_allowed("split-complete", "Working", "Working")
    # Per-L evaluating is not a session transition
    assert not is_allowed("start-evaluating", "Working", "ReadyForDelivery")
