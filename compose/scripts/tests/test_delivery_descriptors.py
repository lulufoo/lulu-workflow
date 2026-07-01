#!/usr/bin/env python3
"""Tests for delivery_descriptors manifest."""

from __future__ import annotations

import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from delivery_descriptors import iter_delivery_descriptors  # noqa: E402


def test_iter_delivery_includes_diagnostic_from_manifest():
    stages = {d.stage_name for d in iter_delivery_descriptors()}
    assert "lulu-bet" in stages
    assert "lulu-approach" in stages
    assert "lulu-plan" in stages
    assert "lulu-spec" in stages
