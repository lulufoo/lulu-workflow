#!/usr/bin/env python3
"""Tests for scope_refs snapshot and StartAdapter.resolve_scope_refs."""

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
from delivered_refs_schema import (  # noqa: E402
    DeliveredRef,
    parse_scope_refs,
    primary_scope_ref_from_state,
    serialize_delivered_refs,
)
from product_spec_start_adapter import ProductSpecStartAdapter  # noqa: E402
from tech_design_start_adapter import TechDesignStartAdapter  # noqa: E402
from tech_plan_start_adapter import TechPlanStartAdapter  # noqa: E402


def test_primary_scope_ref_from_state():
    state = {
        "scope_refs": serialize_delivered_refs(
            [
                DeliveredRef(type="tech-design", path="/abs/design.md"),
                DeliveredRef(type="product-spec", path="/abs/product.md"),
            ],
        ),
    }
    ref = primary_scope_ref_from_state(state)
    assert ref is not None
    assert ref.type == "tech-design"
    assert parse_scope_refs(state)[1].type == "product-spec"


def test_tech_plan_resolve_scope_refs_primary_tech_chain():
    adapter = TechPlanStartAdapter()
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(type="tech-diagnostic", path="/abs/decision.md"),
            DeliveredRef(type="tech-design", path="/abs/design.md"),
        ],
        run_mode="tech",
    )
    assert len(refs) == 1
    assert refs[0].type == "tech-design"


def test_tech_plan_resolve_scope_refs_appends_product_spec():
    adapter = TechPlanStartAdapter()
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(type="tech-diagnostic", path="/abs/decision.md"),
            DeliveredRef(type="product-spec", path="/abs/product.md"),
        ],
        run_mode="product",
    )
    assert len(refs) == 2
    assert refs[0].type == "tech-diagnostic"
    assert refs[1].type == "product-spec"


def test_tech_design_resolve_scope_refs():
    adapter = TechDesignStartAdapter()
    refs = adapter.resolve_scope_refs(
        delivered_refs=[DeliveredRef(type="tech-diagnostic", path="/abs/decision.md")],
        run_mode="tech",
    )
    assert len(refs) == 1
    assert refs[0].type == "tech-diagnostic"


def test_product_spec_resolve_scope_refs():
    adapter = ProductSpecStartAdapter()
    refs = adapter.resolve_scope_refs(
        delivered_refs=[DeliveredRef(type="product-diagnostic", path="/abs/decision.md")],
        run_mode="product",
    )
    assert len(refs) == 1
    assert refs[0].type == "product-diagnostic"
