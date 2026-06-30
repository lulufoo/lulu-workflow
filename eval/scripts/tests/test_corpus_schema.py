#!/usr/bin/env python3
"""Tests for eval/scripts/corpus_schema.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tech-plan" / "scripts"))

from corpus_compose import COMPOSED_CORPUS_REF, compose_corpus, load_dimension_def  # noqa: E402
from corpus_schema import (  # noqa: E402
    corpus_ref,
    default_dimension_defs_dir,
    dispatch_ids,
    expand_corpus,
    get_schema,
    resolve_dim_id,
    validate_corpus,
)

_DIMENSION_DEFS = default_dimension_defs_dir()


def _feature_tech_upstream_corpus() -> dict:
    dims = [
        load_dimension_def(_DIMENSION_DEFS / "codebase-consistency.json"),
        load_dimension_def(_DIMENSION_DEFS / "solution-quality.json"),
        load_dimension_def(_DIMENSION_DEFS / "tech-conformance.json"),
    ]
    return compose_corpus(
        corpus_id="tech-plan-composed",
        corpus_version="1",
        scope="tech-plan",
        dimensions=dims,
    )


def _feature_base_corpus() -> dict:
    dims = [
        load_dimension_def(_DIMENSION_DEFS / "codebase-consistency.json"),
        load_dimension_def(_DIMENSION_DEFS / "solution-quality.json"),
    ]
    return compose_corpus(
        corpus_id="tech-plan-composed",
        corpus_version="1",
        scope="tech-plan",
        dimensions=dims,
    )


class TestGetSchema:
    def test_has_bind_placeholders(self):
        schema = get_schema()
        assert schema["bind_placeholders"] == ["compose_doc", "product_ref", "cycle_type", "M"]
        assert schema["enums"]["sot_kind"] == ["url", "codebase"]
        assert schema["enums"]["codebase_strategy"] == ["all"]


class TestValidateCorpus:
    def test_feature_tech_upstream_corpus_valid(self):
        assert validate_corpus(_feature_tech_upstream_corpus()) == []

    def test_feature_base_corpus_valid(self):
        assert validate_corpus(_feature_base_corpus()) == []

    def test_missing_dimensions(self):
        errors = validate_corpus({"id": "x", "version": "3"})
        assert any("dimensions" in err for err in errors)

    def test_duplicate_dimension_id(self):
        dim = {
            "id": "a",
            "label": "A",
            "eval_target": {"path": "{compose_doc}"},
            "remediation_target": {"path": "{compose_doc}"},
            "sots": [],
            "method": {
                "kind": "external",
                "source": "https://example.com/rubric.md",
                "focus": "f",
            },
            "review": {"seq": 1, "output_path": "r.md", "template": "eval/review.template.md"},
        }
        errors = validate_corpus(
            {
                "id": "x",
                "version": "3",
                "scope": "tech-plan",
                "context": "offline",
                "dimension_dispatch": "parallel",
                "dimensions": [dim, dict(dim)],
            },
        )
        assert any("duplicate dimension id" in err for err in errors)


class TestExpandCorpus:
    _BIND = {
        "compose_doc": "/abs/tech-doc.md",
        "product_ref": "/abs/product-doc.md",
        "cycle_type": "feature",
        "M": "1",
        "tpt_intent_eval_framework_url": "https://github.com/o/r/blob/main/41-tech-plan-intent-evaluation-framework.md",
        "tpt_tech_conformance_url": "https://github.com/o/r/blob/main/tech-conformance.md",
        "upstream_doc_path": "/abs/design-doc.md",
    }

    def test_expand_substitutes_tech_conformance_paths(self):
        data = _feature_tech_upstream_corpus()
        expanded = expand_corpus(data, self._BIND)
        e4 = expanded["dimensions"][2]
        assert e4["eval_target"]["path"] == "/abs/tech-doc.md"
        assert e4["sots"][0]["ref"] == "/abs/design-doc.md"
        assert e4["method"]["source"] == self._BIND["tpt_tech_conformance_url"]
        assert e4["review"]["output_path"] == "tech-review-e13.md"

    def test_expand_preserves_codebase_root_dot(self):
        data = _feature_base_corpus()
        expanded = expand_corpus(data, self._BIND)
        e2 = expanded["dimensions"][0]
        assert e2["sots"][0]["ref"] == {"root": ".", "strategy": "all"}

    def test_expand_e3_substitutes_intent_probe_urls(self):
        data = _feature_tech_upstream_corpus()
        expanded = expand_corpus(data, self._BIND)
        e3 = expanded["dimensions"][1]
        assert e3["sots"][0]["ref"] == self._BIND["tpt_intent_eval_framework_url"]
        assert e3["method"]["source"] == {"procedure_id": "intent_gap_probes"}

    def test_invalid_codebase_strategy(self):
        dim = {
            "id": "a",
            "label": "A",
            "eval_target": {"path": "{compose_doc}"},
            "remediation_target": {"path": "{compose_doc}"},
            "sots": [
                {
                    "kind": "codebase",
                    "role": "primary",
                    "ref": {"root": ".", "strategy": "glob:**"},
                },
            ],
            "method": {
                "kind": "builtin",
                "source": {"procedure_id": "codebase_consistency"},
                "focus": "f",
            },
            "review": {"seq": 1, "output_path": "r.md", "template": "eval/review.template.md"},
        }
        errors = validate_corpus(
            {
                "id": "x",
                "version": "3",
                "scope": "tech-plan",
                "context": "offline",
                "dimension_dispatch": "parallel",
                "dimensions": [dim],
            },
        )
        assert any("invalid codebase strategy" in err for err in errors)

    def test_unbound_placeholder_raises(self):
        data = _feature_tech_upstream_corpus()
        with pytest.raises(ValueError, match="unbound placeholder"):
            expand_corpus(data, {"compose_doc": "/abs/tech-doc.md"})


class TestHelpers:
    def test_corpus_ref(self):
        data = _feature_tech_upstream_corpus()
        assert corpus_ref(data) == COMPOSED_CORPUS_REF

    def test_dispatch_ids(self):
        data = _feature_base_corpus()
        assert dispatch_ids(data) == ["codebase-consistency", "solution-quality"]

    def test_resolve_dim_id_legacy_alias(self):
        data = _feature_tech_upstream_corpus()
        assert resolve_dim_id(data, "e2") == "codebase-consistency"
        assert resolve_dim_id(data, "e4") == "tech-conformance"
        assert resolve_dim_id(data, "codebase-consistency") == "codebase-consistency"

    def test_resolve_unknown_dim(self):
        data = _feature_tech_upstream_corpus()
        with pytest.raises(ValueError, match="unknown dimension"):
            resolve_dim_id(data, "e9")
