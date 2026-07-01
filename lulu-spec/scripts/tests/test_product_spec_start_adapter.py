#!/usr/bin/env python3
"""Tests for lulu-spec StartAdapter."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401
from delivered_refs_schema import (  # noqa: E402
    record_delivered_ref,
)
from product_spec_start_adapter import ProductSpecStartAdapter  # noqa: E402


def _seed_product_diagnostic(tmp_path: Path, cycle_id: str) -> Path:
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


def test_validate_rejects_topic_cycle(tmp_path: Path) -> None:
    adapter = ProductSpecStartAdapter()
    errors = adapter.validate_for_start(
        "topic-demo",
        tmp_path,
        run_mode="product",
    )
    assert errors == ["lulu-spec is feature-only; topic cycles are not supported"]


def test_validate_requires_product_diagnostic(tmp_path: Path) -> None:
    adapter = ProductSpecStartAdapter()
    errors = adapter.validate_for_start(
        "feat-a",
        tmp_path,
        run_mode="product",
    )
    assert errors == ["missing delivered-refs entry: lulu-bet"]


def test_resolve_delivered_refs_product_diagnostic(tmp_path: Path) -> None:
    cycle_id = "feat-spec-start"
    decision = _seed_product_diagnostic(tmp_path, cycle_id)
    adapter = ProductSpecStartAdapter()
    assert adapter.validate_for_start(cycle_id, tmp_path, run_mode="product") == []
    refs = adapter.resolve_delivered_refs(cycle_id, tmp_path, run_mode="product")
    assert len(refs) == 1
    assert refs[0].type == "lulu-bet"
    assert refs[0].path == str(decision.resolve())
