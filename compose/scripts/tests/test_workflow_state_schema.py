#!/usr/bin/env python3
"""Tests for lulu-plan workflow_state_schema.py."""

import json
import sys
from pathlib import Path

import pytest

import bootstrap  # noqa: F401
from bootstrap import CORE, SCHEMA_SESSION  # noqa: E402

from delivered_refs_schema import DeliveredRef, delivered_path, parse_delivered_refs
from workflow_state_schema import (
    get_schema,
    init_drafting,
    load_workflow_state,
    mark_historical,
    mark_invalidated,
    read_current_state,
    resolve_workflow_state_path_from_cycle,
    save_workflow_state,
    validate_workflow_state,
)
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, seed_profile_pointer_for_tests  # noqa: E402

_REQUIRED_FIELD_NAMES = {
    "version",
    "workflow",
    "mode",
    "cycle_type",
    "current_state",
    "evaluate_round",
    "delivered_refs",
    "carry_forward_ref",
    "updated_at",
}

_VALID_DATA = {
    "version": "1",
    "workflow": "tech-doc",
    "mode": "product",
    "cycle_type": "feature",
    "current_state": "Drafting",
    "evaluate_round": "0",
    "delivered_refs": '[{"type":"lulu-spec","path":"/path/to/product-doc.md"}]',
    "carry_forward_ref": "",
    "updated_at": "2024-01-01T00:00:00+00:00",
}


class TestGetSchema:
    def test_contains_all_required_fields(self):
        field_names = {s["field"] for s in get_schema()}
        assert _REQUIRED_FIELD_NAMES.issubset(field_names)

    def test_historical_is_optional(self):
        historical = next(s for s in get_schema() if s["field"] == "historical")
        assert historical["required"] is False


class TestValidateWorkflowState:
    def test_valid_data_returns_empty(self):
        assert validate_workflow_state(_VALID_DATA) == []

    def test_missing_required_field(self):
        data = {k: v for k, v in _VALID_DATA.items() if k != "mode"}
        errors = validate_workflow_state(data)
        assert any("mode" in e for e in errors)

    def test_invalid_current_state(self):
        data = {**_VALID_DATA, "current_state": "NotAState"}
        errors = validate_workflow_state(data)
        assert any("current_state" in e for e in errors)

    def test_delivered_rejects_skip_evaluate_requested(self):
        data = {
            **_VALID_DATA,
            "current_state": "Delivered",
            "skip_evaluate_requested": "true",
        }
        errors = validate_workflow_state(data)
        assert any("skip_evaluate_requested" in e for e in errors)


class TestInitDrafting:
    def test_writes_valid_drafting_state(self, tmp_path: Path):
        path = tmp_path / "revision1" / "workflow-state.md"
        refs = [DeliveredRef(type="lulu-approach", path="/abs/decision.md")]
        init_drafting(
            path,
            mode="tech",
            delivered_refs=refs,
            carry_forward_ref="/old/tech-doc.md",
        )
        loaded = load_workflow_state(path)
        assert loaded["current_state"] == "Drafting"
        assert loaded["mode"] == "tech"
        assert loaded["cycle_type"] == "feature"
        assert loaded["evaluate_round"] == "0"
        assert loaded["carry_forward_ref"] == "/old/tech-doc.md"
        assert delivered_path(loaded, "lulu-approach") == "/abs/decision.md"


class TestMarkHistorical:
    def test_idempotent(self, tmp_path: Path):
        path = tmp_path / "workflow-state.md"
        init_drafting(
            path,
            mode="product",
            delivered_refs=[DeliveredRef(type="lulu-spec", path="/p.md")],
        )
        save_workflow_state(path, {"current_state": "Delivered"})
        mark_historical(path)
        first = load_workflow_state(path)
        mark_historical(path)
        second = load_workflow_state(path)
        assert first["historical"] == "true"
        assert second["historical"] == "true"


class TestMarkInvalidated:
    def test_preserves_other_fields(self, tmp_path: Path):
        path = tmp_path / "workflow-state.md"
        init_drafting(
            path,
            mode="product",
            delivered_refs=[DeliveredRef(type="lulu-spec", path="/p.md")],
        )
        mark_invalidated(path)
        loaded = load_workflow_state(path)
        assert loaded["current_state"] == "Invalidated"
        assert delivered_path(loaded, "lulu-spec") == "/p.md"


class TestReadCurrentState:
    def test_missing_file_returns_default(self, tmp_path: Path):
        assert read_current_state(tmp_path / "missing.md", default="Drafting") == "Drafting"


class TestResolveWorkflowStatePathFromCycle:
    def test_resolves_active_doc(self, tmp_path: Path):
        cycle_id = "feat-a"
        seed_profile_pointer_for_tests(tmp_path, cycle_id, DEFAULT_COMPOSE_PROFILE_ID)
        base = tmp_path / ".cache" / "cursor" / "lulu-dev-workflow" / cycle_id / "lulu-plan"
        base.mkdir(parents=True, exist_ok=True)
        (base / "session-state.md").write_text(
            "---\nversion: 1\nactive_doc: 2\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
            encoding="utf-8",
        )
        path = resolve_workflow_state_path_from_cycle(cycle_id, tmp_path)
        assert path.name == "workflow-state.md"
        assert path.parent.name == "revision2"


class TestSaveLoadRoundTrip:
    def test_merge_preserves_unmentioned_fields(self, tmp_path: Path):
        path = tmp_path / "workflow-state.md"
        init_drafting(
            path,
            mode="product",
            delivered_refs=[DeliveredRef(type="lulu-spec", path="/p.md")],
        )
        save_workflow_state(path, {"current_state": "Evaluating", "evaluate_round": "1"})
        loaded = load_workflow_state(path)
        assert loaded["current_state"] == "Evaluating"
        assert delivered_path(loaded, "lulu-spec") == "/p.md"


class TestCli:
    def test_schema_flag(self):
        import subprocess

        script = SCHEMA_SESSION / "workflow_state_schema.py"
        result = subprocess.run(
            [sys.executable, str(script), "--schema"],
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(result.stdout)
        assert isinstance(payload, list)
