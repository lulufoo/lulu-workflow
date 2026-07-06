#!/usr/bin/env python3
"""Tests for lulu-blueprint StartAdapter."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401
from delivered_refs_schema import record_delivered_ref  # noqa: E402
from product_blueprint_start_adapter import ProductBlueprintStartAdapter  # noqa: E402


def _seed_product_decision(tmp_path: Path, cycle_id: str) -> Path:
    diag_dir = tmp_path / ".cache/cursor/lulu-dev-workflow" / cycle_id / "lulu-bet"
    diag_dir.mkdir(parents=True)
    decision = diag_dir / "decision-doc.md"
    decision.write_text("# Decision\n", encoding="utf-8")
    (diag_dir / "session-state.md").write_text(
        "---\ncurrent_state: Delivered\n---\n",
        encoding="utf-8",
    )
    record_delivered_ref(
        cycle_id,
        tmp_path,
        delivered_type="lulu-bet",
        path=str(decision.resolve()),
        revision=1,
        profile_id="lulu-bet",
        source_workflow_state=str((diag_dir / "session-state.md").resolve()),
    )
    return decision


def test_infer_run_mode_is_product(tmp_path: Path) -> None:
    adapter = ProductBlueprintStartAdapter()
    assert adapter.infer_run_mode("topic-demo", tmp_path) == "product"


def test_validate_rejects_feature_cycle(tmp_path: Path) -> None:
    adapter = ProductBlueprintStartAdapter()
    errors = adapter.validate_for_start(
        "feat-a",
        tmp_path,
        run_mode="product",
    )
    assert errors == ["lulu-blueprint is topic-only; feature cycles use lulu-spec"]


def test_validate_rejects_non_product_run_mode(tmp_path: Path) -> None:
    adapter = ProductBlueprintStartAdapter()
    errors = adapter.validate_for_start(
        "topic-demo",
        tmp_path,
        run_mode="tech",
    )
    assert errors == ["invalid run_mode: 'tech' (lulu-blueprint is product-only)"]


def test_validate_requires_lulu_bet(tmp_path: Path) -> None:
    adapter = ProductBlueprintStartAdapter()
    errors = adapter.validate_for_start(
        "topic-demo",
        tmp_path,
        run_mode="product",
    )
    assert errors == ["missing delivered-refs entry: lulu-bet"]


def test_resolve_delivered_refs_lulu_bet(tmp_path: Path) -> None:
    cycle_id = "topic-blueprint-start"
    decision = _seed_product_decision(tmp_path, cycle_id)
    adapter = ProductBlueprintStartAdapter()
    assert adapter.validate_for_start(cycle_id, tmp_path, run_mode="product") == []
    refs = adapter.resolve_delivered_refs(cycle_id, tmp_path, run_mode="product")
    assert len(refs) == 1
    assert refs[0].type == "lulu-bet"
    assert refs[0].path == str(decision.resolve())
