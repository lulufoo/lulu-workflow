#!/usr/bin/env python3
"""Tests for Phase B compose_session helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import bootstrap  # noqa: F401
from bootstrap import CORE  # noqa: E402

sys.path.insert(0, str(CORE))
from compose_session import calibration_note  # noqa: E402

_CYCLE = "feature-phaseb001-abc12345"


class TestCalibrationNote:
    def test_tech_design(self):
        note = calibration_note("tech-design", "tech")
        assert "d1" in note and "d2" in note

    def test_tech_plan_product(self):
        note = calibration_note("tech-plan", "product")
        assert "product-doc" in note

    def test_tech_plan_tech_mode(self):
        note = calibration_note("tech-plan", "tech")
        assert "E2" in note
