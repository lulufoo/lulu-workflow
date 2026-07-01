#!/usr/bin/env python3
"""Tests for after_dc messaging from transition-table.json."""

from __future__ import annotations

import sys
from pathlib import Path

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dec_after_dc import build_after_dc, next_steps_for_stage  # noqa: E402


def test_next_steps_product_diagnostic_feature() -> None:
    assert next_steps_for_stage("lulu-bet", "feature") == ["lulu-spec"]


def test_next_steps_product_diagnostic_topic() -> None:
    assert next_steps_for_stage("lulu-bet", "topic") == ["lulu-blueprint"]


def test_next_steps_tech_diagnostic_feature() -> None:
    assert next_steps_for_stage("lulu-approach", "feature") == ["lulu-design", "lulu-plan"]


def test_build_after_dc_message_uses_raw_stage_ids() -> None:
    payload = build_after_dc("lulu-bet", "feature")
    assert payload["next_steps"] == ["lulu-spec"]
    assert payload["user_message"] == (
        "lulu-bet is complete. The next step is: lulu-spec."
    )


def test_build_after_dc_terminal_stage() -> None:
    payload = build_after_dc("lulu-arch", "topic")
    assert payload["next_steps"] == []
    assert payload["user_message"] == "lulu-arch is complete."
