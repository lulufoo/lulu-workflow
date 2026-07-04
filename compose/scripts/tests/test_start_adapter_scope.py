#!/usr/bin/env python3
"""Tests for scope_refs snapshot and StartAdapter.resolve_scope_refs."""

from __future__ import annotations

import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
for _rel in (
    "compose/scripts/start",
    "lulu-plan/scripts/start",
    "lulu-design/scripts/start",
    "lulu-spec/scripts/start",
):
    _p = _WORKFLOW_ROOT / _rel
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bootstrap  # noqa: F401
from delivered_refs_schema import DeliveredRef  # noqa: E402
from product_spec_start_adapter import ProductSpecStartAdapter  # noqa: E402
from tech_design_start_adapter import TechDesignStartAdapter  # noqa: E402
from tech_plan_start_adapter import TechPlanStartAdapter  # noqa: E402


def test_tech_plan_resolve_scope_refs_primary_tech_chain():
    adapter = TechPlanStartAdapter()
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(type="lulu-approach", path="/abs/decision.md"),
            DeliveredRef(type="lulu-design", path="/abs/design.md"),
        ],
        run_mode="tech",
    )
    assert len(refs) == 1
    assert refs[0].type == "lulu-design"


def test_tech_plan_resolve_scope_refs_primary_only_with_product_delivered():
    adapter = TechPlanStartAdapter()
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(type="lulu-approach", path="/abs/decision.md"),
            DeliveredRef(type="lulu-spec", path="/abs/product.md"),
        ],
        run_mode="product",
    )
    assert len(refs) == 1
    assert refs[0].type == "lulu-approach"


def test_tech_design_resolve_scope_refs():
    adapter = TechDesignStartAdapter()
    refs = adapter.resolve_scope_refs(
        delivered_refs=[DeliveredRef(type="lulu-approach", path="/abs/decision.md")],
        run_mode="tech",
    )
    assert len(refs) == 1
    assert refs[0].type == "lulu-approach"


def test_product_spec_resolve_scope_refs():
    adapter = ProductSpecStartAdapter()
    refs = adapter.resolve_scope_refs(
        delivered_refs=[DeliveredRef(type="lulu-bet", path="/abs/decision.md")],
        run_mode="product",
    )
    assert len(refs) == 1
    assert refs[0].type == "lulu-bet"


def test_tech_design_scope_excludes_spec_in_product_mode():
    adapter = TechDesignStartAdapter()
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(type="lulu-approach", path="/abs/decision.md"),
            DeliveredRef(type="lulu-spec", path="/abs/product.md"),
        ],
        run_mode="product",
    )
    assert [r.type for r in refs] == ["lulu-approach"]


def test_tech_design_intent_baseline_is_spec_when_present():
    adapter = TechDesignStartAdapter()
    refs = adapter.resolve_intent_baseline_refs(
        delivered_refs=[
            DeliveredRef(type="lulu-approach", path="/abs/decision.md"),
            DeliveredRef(type="lulu-spec", path="/abs/product.md"),
        ],
        run_mode="product",
    )
    assert [r.type for r in refs] == ["lulu-spec"]


def test_tech_design_intent_baseline_empty_without_spec():
    adapter = TechDesignStartAdapter()
    refs = adapter.resolve_intent_baseline_refs(
        delivered_refs=[DeliveredRef(type="lulu-approach", path="/abs/decision.md")],
    )
    assert refs == []


def test_tech_design_norm_constraint_empty():
    adapter = TechDesignStartAdapter()
    assert adapter.resolve_norm_constraint_refs() == []
