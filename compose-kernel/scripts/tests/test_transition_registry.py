#!/usr/bin/env python3
"""Tests for transition_registry.py."""

from __future__ import annotations

import bootstrap  # noqa: F401
from transition_registry import is_allowed, load_transition_table, session_states


def test_load_transition_table():
    data = load_transition_table()
    assert "states" in data
    assert "transitions" in data
    assert len(data["transitions"]) == 6


def test_session_states_match_whitelist():
    states = session_states()
    assert states == frozenset(
        {
            "Drafting",
            "Evaluating",
            "ReadyForDelivery",
            "Delivered",
            "Invalidated",
        }
    )


def test_allowed_transitions():
    assert is_allowed("start-evaluating", "Drafting", "Evaluating")
    assert is_allowed("ready-for-delivery", "Drafting", "ReadyForDelivery")
    assert is_allowed("ready-for-delivery", "Evaluating", "ReadyForDelivery")
    assert is_allowed("abandon-evaluation", "Evaluating", "Drafting")
    assert is_allowed("resume-after-eval", "Evaluating", "Drafting")
    assert is_allowed("deliver", "ReadyForDelivery", "Delivered")


def test_disallowed_transitions():
    assert not is_allowed("deliver", "Drafting", "Delivered")
    assert not is_allowed("start-evaluating", "ReadyForDelivery", "Evaluating")
    assert not is_allowed("abandon-evaluation", "Drafting", "Drafting")
    assert not is_allowed("resume-after-eval", "Drafting", "Evaluating")
