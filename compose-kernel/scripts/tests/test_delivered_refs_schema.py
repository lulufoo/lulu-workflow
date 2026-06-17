#!/usr/bin/env python3
"""Tests for delivered_refs_schema helpers."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401
from delivered_refs_schema import (  # noqa: E402
    DeliveredRef,
    init_scope_ref_from_state,
    load_delivered_refs_file,
)
from delivered_refs_backfill import backfill_delivered_refs_from_cycle  # noqa: E402
from delivered_refs_schema import serialize_delivered_refs  # noqa: E402


def test_init_scope_ref_tech_plan_product_mode():
    state = {
        "mode": "product",
        "delivered_refs": serialize_delivered_refs(
            [
                DeliveredRef(type="product-plan", path="/abs/product-doc.md"),
                DeliveredRef(type="tech-diagnostic", path="/abs/decision.md"),
            ],
        ),
    }
    ref = init_scope_ref_from_state(state, "tech-plan")
    assert ref is not None
    assert ref.type == "product-plan"
    assert ref.path == "/abs/product-doc.md"


def test_init_scope_ref_tech_plan_tech_mode_prefers_design():
    state = {
        "mode": "tech",
        "delivered_refs": serialize_delivered_refs(
            [
                DeliveredRef(type="tech-diagnostic", path="/abs/decision.md"),
                DeliveredRef(type="tech-design", path="/abs/design.md"),
            ],
        ),
    }
    ref = init_scope_ref_from_state(state, "tech-plan")
    assert ref is not None
    assert ref.type == "tech-design"


def test_init_scope_ref_tech_design():
    state = {
        "mode": "tech",
        "delivered_refs": serialize_delivered_refs(
            [DeliveredRef(type="tech-diagnostic", path="/abs/decision.md")],
        ),
    }
    ref = init_scope_ref_from_state(state, "tech-design")
    assert ref is not None
    assert ref.type == "tech-diagnostic"


def test_backfill_from_delivered_tech_diagnostic(tmp_path: Path):
    cycle_id = "feat-backfill-diag"
    diag_dir = tmp_path / ".cache/cursor/lulu-dev-workflow" / cycle_id / "tech" / "diagnostic"
    diag_dir.mkdir(parents=True)
    decision = diag_dir / "decision-doc.md"
    decision.write_text("# Decision\n", encoding="utf-8")
    (diag_dir / "session-state.md").write_text(
        "---\ncurrent_state: Delivered\nupdated_at: 2026-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    backfill_delivered_refs_from_cycle(cycle_id, tmp_path)
    data = load_delivered_refs_file(cycle_id, tmp_path)
    entry = data["entries"]["tech-diagnostic"]
    assert entry["path"] == str(decision.resolve())


def test_backfill_from_delivered_product_plan(tmp_path: Path):
    cycle_id = "feat-backfill-plan"
    rev = tmp_path / ".cache/cursor/lulu-dev-workflow" / cycle_id / "product" / "plan" / "revision1"
    rev.mkdir(parents=True)
    product_doc = rev / "product-doc.md"
    product_doc.write_text("# Product\n", encoding="utf-8")
    (rev / "workflow-state.md").write_text(
        "---\n"
        "version: 1\n"
        "workflow: product-doc\n"
        "mode: product\n"
        "cycle_type: feature\n"
        "current_state: Delivered\n"
        "evaluate_round: 0\n"
        "delivered_refs: []\n"
        "carry_forward_ref: \"\"\n"
        "updated_at: 2026-01-02T00:00:00+00:00\n"
        "---\n",
        encoding="utf-8",
    )
    backfill_delivered_refs_from_cycle(cycle_id, tmp_path)
    data = load_delivered_refs_file(cycle_id, tmp_path)
    assert data["entries"]["product-plan"]["path"] == str(product_doc.resolve())
