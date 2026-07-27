#!/usr/bin/env python3
"""Tests for delivered_refs_schema helpers."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401
from delivered_refs_schema import (  # noqa: E402
    load_delivered_refs_file,
)
from delivered_refs_backfill import backfill_delivered_refs_from_cycle  # noqa: E402


def test_backfill_from_delivered_tech_diagnostic(tmp_path: Path):
    cycle_id = "feat-backfill-diag"
    diag_dir = tmp_path / ".cache/cursor/lulu-dev-workflow" / cycle_id / "lulu-approach"
    diag_dir.mkdir(parents=True)
    decision = diag_dir / "decision-doc.md"
    decision.write_text("# Decision\n", encoding="utf-8")
    decision_fact = diag_dir / "decision-fact.json"
    decision_fact.write_text(
        '{"version":1,"gates":{"Q":[{"id":"Q-1","text":"problem","slot":"Q.problem_statement"}]}}\n',
        encoding="utf-8",
    )
    (diag_dir / "session-state.md").write_text(
        "---\ncurrent_state: Delivered\nupdated_at: 2026-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    backfill_delivered_refs_from_cycle(cycle_id, tmp_path)
    data = load_delivered_refs_file(cycle_id, tmp_path)
    entry = data["entries"]["lulu-approach"]
    assert entry["path"] == str(decision.resolve())
    assert entry["decision_fact_path"] == str(decision_fact.resolve())


def test_backfill_from_delivered_tech_design(tmp_path: Path):
    cycle_id = "feat-backfill-design"
    rev = tmp_path / ".cache/cursor/lulu-dev-workflow" / cycle_id / "lulu-design" / "revision1"
    rev.mkdir(parents=True)
    (rev / "L1").mkdir()
    (rev / "L1" / "design-doc.md").write_text("# Design\n", encoding="utf-8")
    package = rev / "design-package.json"
    package.write_text(
        '{"version":1,"profile_id":"lulu-design","order":["L1"],'
        '"slices":[{"id":"L1","title":"Only","doc_path":"L1/design-doc.md"}]}\n',
        encoding="utf-8",
    )
    facts = rev / "_facts.json"
    facts.write_text("[]\n", encoding="utf-8")
    (rev / "workflow-state.md").write_text(
        "---\n"
        "version: 1\n"
        "workflow: lulu-design\n"
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
    assert data["entries"]["lulu-design"]["path"] == str(package.resolve())
    assert "facts_path" not in data["entries"]["lulu-design"]
    assert "lulu-design-facts" not in data["entries"]
    assert facts.is_file()  # local process artifact may exist; not delivered


def test_backfill_from_delivered_product_spec(tmp_path: Path):
    cycle_id = "feat-backfill-spec"
    rev = tmp_path / ".cache/cursor/lulu-dev-workflow" / cycle_id / "lulu-spec" / "revision1"
    rev.mkdir(parents=True)
    (rev / "L1").mkdir()
    (rev / "L1" / "product-doc.md").write_text("# Product\n", encoding="utf-8")
    package = rev / "product-package.json"
    package.write_text(
        '{"version":1,"profile_id":"lulu-spec","order":["L1"],'
        '"slices":[{"id":"L1","title":"Only","doc_path":"L1/product-doc.md"}]}\n',
        encoding="utf-8",
    )
    (rev / "workflow-state.md").write_text(
        "---\n"
        "version: 1\n"
        "workflow: lulu-spec\n"
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
    assert data["entries"]["lulu-spec"]["path"] == str(package.resolve())


def test_backfill_plan_with_facts_file_does_not_register_design_facts(tmp_path: Path):
    cycle_id = "feat-backfill-plan-facts"
    rev = tmp_path / ".cache/cursor/lulu-dev-workflow" / cycle_id / "lulu-plan" / "revision1"
    rev.mkdir(parents=True)
    (rev / "L1").mkdir()
    (rev / "L1" / "tech-doc.md").write_text("# Tech\n", encoding="utf-8")
    package = rev / "tech-package.json"
    package.write_text(
        '{"version":1,"profile_id":"lulu-plan","order":["L1"],'
        '"slices":[{"id":"L1","title":"Only","doc_path":"L1/tech-doc.md"}]}\n',
        encoding="utf-8",
    )
    (rev / "_facts.json").write_text("[]\n", encoding="utf-8")
    (rev / "workflow-state.md").write_text(
        "---\n"
        "version: 1\n"
        "workflow: lulu-plan\n"
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
    assert data["entries"]["lulu-plan"]["path"] == str(package.resolve())
    assert "facts_path" not in data["entries"]["lulu-plan"]
    assert "lulu-design-facts" not in data["entries"]
    assert "lulu-plan-facts" not in data["entries"]
