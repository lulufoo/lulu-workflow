#!/usr/bin/env python3
"""Tests for StartAdapter.post_start_guidance."""

from __future__ import annotations

import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
for _rel in (
    "compose-kernel/scripts/start",
    "tech-plan/scripts/start",
    "tech-design/scripts/start",
    "product-spec/scripts/start",
):
    _p = _WORKFLOW_ROOT / _rel
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bootstrap  # noqa: F401
from product_spec_start_adapter import ProductSpecStartAdapter  # noqa: E402
from tech_design_start_adapter import TechDesignStartAdapter  # noqa: E402
from tech_plan_start_adapter import TechPlanStartAdapter  # noqa: E402


def test_tech_design_post_start_guidance():
    note = TechDesignStartAdapter().post_start_guidance(
        run_mode="tech",
        carry_forward_ref="",
        scope_refs=[],
    )
    assert "设计阶段" in note


def test_tech_plan_product_mode_guidance():
    note = TechPlanStartAdapter().post_start_guidance(
        run_mode="product",
        carry_forward_ref="",
        scope_refs=[],
    )
    assert "产品需求模式" in note


def test_tech_plan_tech_mode_guidance():
    note = TechPlanStartAdapter().post_start_guidance(
        run_mode="tech",
        carry_forward_ref="",
        scope_refs=[],
    )
    assert "技改模式" in note


def test_product_spec_post_start_guidance():
    note = ProductSpecStartAdapter().post_start_guidance(
        run_mode="product",
        carry_forward_ref="",
        scope_refs=[],
    )
    assert "product-diagnostic" in note
