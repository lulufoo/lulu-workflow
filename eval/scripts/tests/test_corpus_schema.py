#!/usr/bin/env python3
"""Tests for the EvalCorpus v6 data contract."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from corpus_compose import compose_corpus  # noqa: E402
from corpus_schema import (  # noqa: E402
    corpus_ref,
    dispatch_ids,
    expand_corpus,
    get_schema,
    normalize_corpus,
    validate_corpus,
)


def _dimension(*, handling_policy: str | None = None) -> dict:
    dimension = {
        "id": "synthetic-quality",
        "label": "Synthetic quality",
        "eval_target": {"path": "{eval_target_path}"},
        "sots": [{"ref": "."}],
        "method": {"ref": "eval/method.md", "focus": "quality"},
        "review": {
            "seq": 1,
            "output_path": "review.md",
            "template": "eval/review.template.md",
        },
    }
    if handling_policy is not None:
        dimension["handling_policy"] = handling_policy
    return dimension


def _corpus(*, handling_policy: str | None = None) -> dict:
    return {
        "id": "synthetic-corpus",
        "schema_version": "6",
        "version": "2",
        "scope": "tests",
        "context": "offline",
        "dimension_dispatch": "parallel",
        "dimensions": [_dimension(handling_policy=handling_policy)],
    }


class TestSchemaAndValidation:
    def test_schema_version_is_separate_from_identity_version(self):
        schema = get_schema()
        assert schema["schema_version"] == "6"
        assert {"schema_version", "version"} <= set(schema["required_top_level"])
        assert corpus_ref(_corpus()) == "synthetic-corpus@2"

    def test_missing_policy_defaults_to_class_default(self):
        normalized = normalize_corpus(_corpus())
        assert normalized["dimensions"][0]["handling_policy"] == "class-default"

    def test_human_first_is_valid_and_other_values_are_rejected(self):
        assert validate_corpus(_corpus(handling_policy="human-first")) == []
        errors = validate_corpus(_corpus(handling_policy="automatic"))
        assert any("invalid handling_policy" in error for error in errors)

    @pytest.mark.parametrize("field", ["force_human_resolution", "remediation_target"])
    def test_removed_dimension_fields_are_rejected(self, field: str):
        corpus = _corpus()
        corpus["dimensions"][0][field] = (
            False if field == "force_human_resolution" else {"path": "target.md"}
        )
        assert any(f"unsupported field: {field!r}" in error for error in validate_corpus(corpus))

    @pytest.mark.parametrize("schema_version", [None, "5", 6])
    def test_old_or_malformed_schema_versions_are_stably_rejected(self, schema_version):
        corpus = _corpus()
        if schema_version is None:
            del corpus["schema_version"]
        else:
            corpus["schema_version"] = schema_version
        assert any("incompatible_round" in error for error in validate_corpus(corpus))

    def test_old_schema_is_rejected_before_business_fields_are_read(self):
        assert validate_corpus({
            "schema_version": "5",
            "dimensions": "legacy-shape",
        }) == [
            "incompatible_round: EvalCorpus schema_version '5' is not supported "
            "(expected '6')",
        ]


class TestNormalizationAndComposition:
    def test_bind_expansion_outputs_explicit_resolved_policy(self):
        expanded = expand_corpus(
            _corpus(),
            {"eval_target_path": "/abs/target.md"},
        )
        assert expanded["dimensions"][0]["eval_target"]["path"] == "/abs/target.md"
        assert expanded["dimensions"][0]["handling_policy"] == "class-default"

    def test_normalization_does_not_mutate_input(self):
        corpus = _corpus()
        before = copy.deepcopy(corpus)
        normalize_corpus(corpus)
        assert corpus == before

    def test_composed_corpus_persists_schema_version_and_normalized_policy(self):
        composed = compose_corpus(
            corpus_id="synthetic-composed",
            corpus_version="2",
            scope="tests",
            dimensions=[_dimension()],
        )
        assert composed["schema_version"] == "6"
        assert composed["version"] == "2"
        assert composed["dimensions"][0]["handling_policy"] == "class-default"
        assert dispatch_ids(composed) == ["synthetic-quality"]

    def test_unbound_placeholder_raises(self):
        with pytest.raises(ValueError, match="unbound placeholder"):
            expand_corpus(_corpus(), {})
