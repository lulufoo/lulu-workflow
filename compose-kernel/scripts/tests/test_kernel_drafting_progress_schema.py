#!/usr/bin/env python3
"""Tests for generic drafting-progress schema."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401
import drafting_progress_schema as schema  # noqa: E402


def test_tech_design_allows_inductive_initialized_and_freeedit() -> None:
    for step in ("Inductive", "Initialized", "FreeEdit"):
        assert schema.validate_drafting_progress(
            {"version": "1", "cycle_id": "C1", "current_step": step},
            profile_id="tech-design",
        ) == []


def test_tech_plan_rejects_inductive() -> None:
    errors = schema.validate_drafting_progress(
        {"version": "1", "cycle_id": "C1", "current_step": "Inductive"},
        profile_id="tech-plan",
    )

    assert any("invalid current_step" in err for err in errors)


def test_product_spec_allows_freeedit() -> None:
    assert schema.validate_drafting_progress(
        {"version": "1", "cycle_id": "C1", "current_step": "FreeEdit"},
        profile_id="product-spec",
    ) == []


def test_save_and_load_drafting_progress(tmp_path: Path) -> None:
    path = tmp_path / "drafting-progress.md"

    schema.save_drafting_progress(
        path,
        {"version": "1", "cycle_id": "C1", "current_step": "Initialized"},
        profile_id="tech-plan",
    )

    assert schema.load_drafting_progress(path, profile_id="tech-plan") == {
        "version": "1",
        "cycle_id": "C1",
        "current_step": "Initialized",
    }


def test_load_normalizes_legacy_ready_to_initialized(tmp_path: Path) -> None:
    path = tmp_path / "drafting-progress.md"
    path.write_text(
        "---\nversion: 1\ncycle_id: C1\ncurrent_step: Ready\n---\n",
        encoding="utf-8",
    )

    assert schema.validate_drafting_progress(
        {"version": "1", "cycle_id": "C1", "current_step": "Ready"},
        profile_id="tech-plan",
    ) == []
    assert schema.load_drafting_progress(path, profile_id="tech-plan")["current_step"] == "Initialized"
    assert schema.read_current_step(path) == "Initialized"
