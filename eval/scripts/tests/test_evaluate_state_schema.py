#!/usr/bin/env python3
"""Tests for eval/scripts/evaluate_state_schema.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_LULU_PLAN_COMPOSED_CORPUS_REF = "lulu-plan-composed@2"
from evaluate_state_schema import (  # noqa: E402
    all_dims_at_least,
    build_initial_evaluate_state,
    get_schema,
    is_v5_state,
    is_v6_state,
    load_evaluate_state,
    parse_dimension_status,
    parse_dimension_tokens,
    parse_issue_counts,
    parse_force_human_resolution,
    save_evaluate_state,
    validate_evaluate_state,
)


def _policy(*dimension_ids: str) -> dict[str, bool]:
    return {dimension_id: False for dimension_id in dimension_ids}


class TestGetSchema:
    def test_version_6(self):
        fields = {item["field"] for item in get_schema()}
        assert "dimension_status" in fields
        assert "dimension_tokens" in fields
        assert "round_token" in fields
        assert "issue_counts" in fields
        assert "corpus_ref" in fields
        assert "force_human_resolution" in fields


class TestBuildInitial:
    def test_builds_pending_dims(self):
        data = build_initial_evaluate_state(
            dimension_ids=["intent-alignment", "codebase-consistency"],
            corpus_ref=_LULU_PLAN_COMPOSED_CORPUS_REF,
            force_human_resolution={
                "intent-alignment": True,
                "codebase-consistency": False,
            },
        )
        assert data["version"] == "6"
        assert data["round_token"]
        assert parse_dimension_tokens(data["dimension_tokens"]) == {}
        dim_map = parse_dimension_status(data["dimension_status"])
        assert dim_map == {
            "intent-alignment": "pending",
            "codebase-consistency": "pending",
        }
        counts = parse_issue_counts(data["issue_counts"])
        assert counts["intent-alignment"] == {"total": "0", "resolved": "0"}
        assert parse_force_human_resolution(data["force_human_resolution"]) == {
            "intent-alignment": True,
            "codebase-consistency": False,
        }

    def test_empty_dimension_ids_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            build_initial_evaluate_state(
                dimension_ids=[],
                force_human_resolution={},
            )

    def test_policy_is_required(self):
        with pytest.raises(TypeError, match="force_human_resolution"):
            build_initial_evaluate_state(dimension_ids=["a"])


class TestValidate:
    def test_valid_initial_state(self):
        data = build_initial_evaluate_state(
            dimension_ids=["a"],
            dimension_dispatch="serial",
            force_human_resolution=_policy("a"),
        )
        assert validate_evaluate_state(data) == []

    def test_invalid_version(self):
        data = build_initial_evaluate_state(
            dimension_ids=["a"],
            force_human_resolution=_policy("a"),
        )
        data["version"] = "2"
        assert any("invalid version" in err for err in validate_evaluate_state(data))

    def test_invalid_dimension_status(self):
        data = build_initial_evaluate_state(
            dimension_ids=["a"],
            force_human_resolution=_policy("a"),
        )
        data["dimension_status"] = '{"a":"bad"}'
        assert validate_evaluate_state(data)

    def test_policy_keys_and_values_are_validated(self):
        data = build_initial_evaluate_state(
            dimension_ids=["a"],
            force_human_resolution=_policy("a"),
        )
        data["force_human_resolution"] = '{"b":true}'
        assert any(
            "keys must match" in error for error in validate_evaluate_state(data)
        )

        data["force_human_resolution"] = '{"a":"true"}'
        assert any(
            "invalid force_human_resolution" in error
            for error in validate_evaluate_state(data)
        )

        data["force_human_resolution"] = ""
        assert any(
            "force_human_resolution" in error
            for error in validate_evaluate_state(data)
        )

    def test_human_resolution_is_valid_and_sot_remediation_is_rejected(self):
        data = build_initial_evaluate_state(
            dimension_ids=["a"],
            force_human_resolution=_policy("a"),
        )
        data["fix_phase"] = "human-resolution"
        assert validate_evaluate_state(data) == []

        data["fix_phase"] = "sot-remediation"
        assert any("invalid fix_phase" in error for error in validate_evaluate_state(data))


class TestIo:
    def test_save_and_load(self, tmp_path: Path):
        path = tmp_path / "evaluate-state.md"
        data = build_initial_evaluate_state(
            dimension_ids=["intent-alignment"],
            corpus_ref=_LULU_PLAN_COMPOSED_CORPUS_REF,
            force_human_resolution=_policy("intent-alignment"),
        )
        save_evaluate_state(path, data, merge=False)
        loaded = load_evaluate_state(path)
        assert loaded["version"] == "6"
        assert loaded["corpus_ref"] == _LULU_PLAN_COMPOSED_CORPUS_REF
        assert is_v6_state(loaded)
        assert not is_v5_state(loaded)


class TestAllDimsAtLeast:
    def test_all_probed(self):
        data = build_initial_evaluate_state(
            dimension_ids=["a", "b"],
            force_human_resolution=_policy("a", "b"),
        )
        data["dimension_status"] = (
            '{"a":"probed","b":"probed"}'
        )
        assert all_dims_at_least(data, ["a", "b"], "probed")

    def test_one_pending(self):
        data = build_initial_evaluate_state(
            dimension_ids=["a", "b"],
            force_human_resolution=_policy("a", "b"),
        )
        data["dimension_status"] = (
            '{"a":"probed","b":"pending"}'
        )
        assert not all_dims_at_least(data, ["a", "b"], "probed")
