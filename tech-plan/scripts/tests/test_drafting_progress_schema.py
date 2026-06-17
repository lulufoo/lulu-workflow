#!/usr/bin/env python3
"""Tests for drafting_progress_schema.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "drafting"))
from drafting_progress_schema import (  # noqa: E402
    get_schema,
    load_drafting_progress,
    resolve_drafting_progress_path_from_cycle,
    save_drafting_progress,
    validate_drafting_progress,
)

_REQUIRED_FIELD_NAMES = {"version", "cycle_id", "current_step"}

_VALID_READY = {
    "version": "1",
    "cycle_id": "feat-test",
    "current_step": "Ready",
}

_VALID_ROUND = {
    **_VALID_READY,
    "current_step": "RoundIteration",
    "round": "1",
}


class TestGetSchema:
    def test_contains_required_fields(self):
        field_names = {s["field"] for s in get_schema()}
        assert _REQUIRED_FIELD_NAMES.issubset(field_names)

    def test_round_is_optional(self):
        round_field = next(s for s in get_schema() if s["field"] == "round")
        assert round_field["required"] is False


class TestValidateDraftingProgress:
    def test_ready_valid(self):
        assert validate_drafting_progress(_VALID_READY) == []

    def test_round_iteration_requires_round(self):
        data = {**_VALID_READY, "current_step": "RoundIteration"}
        errors = validate_drafting_progress(data)
        assert any("round" in e for e in errors)

    def test_invalid_step(self):
        data = {**_VALID_READY, "current_step": "Initializing"}
        errors = validate_drafting_progress(data)
        assert any("current_step" in e for e in errors)


class TestSaveLoad:
    def test_round_trip(self, tmp_path: Path):
        path = tmp_path / "drafting-progress.md"
        save_drafting_progress(path, _VALID_ROUND)
        loaded = load_drafting_progress(path)
        assert loaded["current_step"] == "RoundIteration"
        assert loaded["round"] == "1"

    def test_resolve_from_cycle(self, tmp_path: Path):
        cycle_id = "feat-schema"
        base = tmp_path / ".cache" / "cursor" / "lulu-dev-workflow" / cycle_id / "tech" / "plan"
        revision = base / "revision2"
        revision.mkdir(parents=True)
        (base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 2\n---\n",
            encoding="utf-8",
        )
        path = resolve_drafting_progress_path_from_cycle(cycle_id, tmp_path)
        assert path == revision / "drafting-progress.md"
