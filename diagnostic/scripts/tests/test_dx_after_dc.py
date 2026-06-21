#!/usr/bin/env python3
"""Tests for after_dc messaging from transition-table.json."""

from __future__ import annotations

import sys
from pathlib import Path

_DIAG_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_DIAG_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_DIAG_SCRIPTS))

from dx_after_dc import build_after_dc, next_steps_for_stage  # noqa: E402


def test_next_steps_product_diagnostic_feature() -> None:
    assert next_steps_for_stage("product-diagnostic", "feature") == ["product-spec"]


def test_next_steps_product_diagnostic_topic() -> None:
    assert next_steps_for_stage("product-diagnostic", "topic") == ["product-arch"]


def test_next_steps_tech_diagnostic_feature() -> None:
    assert next_steps_for_stage("tech-diagnostic", "feature") == ["tech-design", "tech-plan"]


def test_build_after_dc_message_uses_raw_stage_ids() -> None:
    payload = build_after_dc("product-diagnostic", "feature")
    assert payload["next_steps"] == ["product-spec"]
    assert payload["user_message"] == (
        "product-diagnostic is complete. The next step is: product-spec."
    )


def test_build_after_dc_terminal_stage() -> None:
    payload = build_after_dc("tech-arch", "topic")
    assert payload["next_steps"] == []
    assert payload["user_message"] == "tech-arch is complete."
