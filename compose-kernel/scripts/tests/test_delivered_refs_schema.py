#!/usr/bin/env python3
"""Tests for delivered_refs_schema helpers."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401
from delivered_refs_schema import (  # noqa: E402
    DeliveredRef,
    load_delivered_refs_file,
    parse_scope_refs,
    primary_scope_ref_from_state,
    serialize_delivered_refs,
)
from delivered_refs_backfill import backfill_delivered_refs_from_cycle  # noqa: E402


def test_parse_scope_refs_primary_index():
    state = {
        "scope_refs": serialize_delivered_refs(
            [DeliveredRef(type="tech-diagnostic", path="/abs/decision.md")],
        ),
    }
    ref = primary_scope_ref_from_state(state)
    assert ref is not None
    assert ref.type == "tech-diagnostic"
    assert len(parse_scope_refs(state)) == 1


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


def test_backfill_from_delivered_tech_design(tmp_path: Path):
    cycle_id = "feat-backfill-design"
    rev = tmp_path / ".cache/cursor/lulu-dev-workflow" / cycle_id / "tech" / "design" / "revision1"
    rev.mkdir(parents=True)
    design_doc = rev / "design-doc.md"
    design_doc.write_text("# Design\n", encoding="utf-8")
    (rev / "workflow-state.md").write_text(
        "---\n"
        "version: 1\n"
        "workflow: tech-design\n"
        "mode: tech\n"
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
    assert data["entries"]["tech-design"]["path"] == str(design_doc.resolve())


def test_backfill_from_delivered_product_spec(tmp_path: Path):
    cycle_id = "feat-backfill-spec"
    rev = tmp_path / ".cache/cursor/lulu-dev-workflow" / cycle_id / "product" / "spec" / "revision1"
    rev.mkdir(parents=True)
    product_doc = rev / "product-doc.md"
    product_doc.write_text("# Product\n", encoding="utf-8")
    (rev / "workflow-state.md").write_text(
        "---\n"
        "version: 1\n"
        "workflow: product-spec\n"
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
    assert data["entries"]["product-spec"]["path"] == str(product_doc.resolve())
