#!/usr/bin/env python3
"""Tests for eval/scripts/corpus_schema.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tech-plan" / "scripts"))

from corpus_compose import COMPOSED_CORPUS_REF, compose_corpus, load_dimension_stamp  # noqa: E402
from corpus_schema import (  # noqa: E402
    corpus_ref,
    default_corpus_dir,
    dispatch_ids,
    expand_corpus,
    get_schema,
    resolve_dim_id,
    validate_corpus,
)

_CORPUS_DIR = default_corpus_dir()
_FEATURE_STAMPS = _CORPUS_DIR / "stamps" / "feature"


def _feature_product_corpus() -> dict:
    dims = [
        load_dimension_stamp(_FEATURE_STAMPS / "intent-alignment.json"),
        load_dimension_stamp(_FEATURE_STAMPS / "codebase-consistency.json"),
        load_dimension_stamp(_FEATURE_STAMPS / "solution-quality.json"),
    ]
    return compose_corpus(
        corpus_id="tech-plan-composed",
        corpus_version="1",
        scope="tech-plan",
        dimensions=dims,
    )


def _feature_tech_corpus() -> dict:
    dims = [
        load_dimension_stamp(_FEATURE_STAMPS / "codebase-consistency.json"),
        load_dimension_stamp(_FEATURE_STAMPS / "solution-quality.json"),
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
        assert "tech_doc" in schema["bind_placeholders"]
        assert "tpt_intent_eval_framework_url" in schema["bind_placeholders"]
        assert schema["enums"]["sot_kind"] == ["url", "codebase"]
        assert schema["enums"]["codebase_strategy"] == ["all"]


class TestValidateCorpus:
    def test_feature_product_corpus_valid(self):
        assert validate_corpus(_feature_product_corpus()) == []

    def test_feature_tech_corpus_valid(self):
        assert validate_corpus(_feature_tech_corpus()) == []

    def test_missing_dimensions(self):
        errors = validate_corpus({"id": "x", "version": "3"})
        assert any("dimensions" in err for err in errors)

    def test_duplicate_dimension_id(self):
        dim = {
            "id": "a",
            "label": "A",
            "eval_target": {"path": "{tech_doc}"},
            "remediation_target": {"path": "{tech_doc}"},
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
        "tech_doc": "/abs/tech-doc.md",
        "product_ref": "/abs/product-doc.md",
        "cycle_type": "feature",
        "M": "1",
        "ptc_url": "https://github.com/o/r/blob/main/ptc.md",
        "tpt_intent_eval_framework_url": "https://github.com/o/r/blob/main/32-tech-plan-intent-evaluation-framework.md",
    }

    def test_expand_substitutes_paths(self):
        data = _feature_product_corpus()
        expanded = expand_corpus(data, self._BIND)
        dim = expanded["dimensions"][0]
        assert dim["eval_target"]["path"] == "/abs/tech-doc.md"
        assert dim["sots"][0]["ref"] == "/abs/product-doc.md"
        assert dim["method"]["source"] == self._BIND["ptc_url"]
        assert dim["review"]["output_path"] == "tech-review-e11.md"

    def test_expand_preserves_codebase_root_dot(self):
        data = _feature_tech_corpus()
        expanded = expand_corpus(data, self._BIND)
        e2 = expanded["dimensions"][0]
        assert e2["sots"][0]["ref"] == {"root": ".", "strategy": "all"}

    def test_expand_e3_substitutes_intent_probe_urls(self):
        data = _feature_product_corpus()
        expanded = expand_corpus(data, self._BIND)
        e3 = expanded["dimensions"][2]
        assert e3["sots"][0]["ref"] == self._BIND["tpt_intent_eval_framework_url"]
        assert e3["method"]["source"] == {"procedure_id": "intent_gap_probes"}

    def test_invalid_codebase_strategy(self):
        dim = {
            "id": "a",
            "label": "A",
            "eval_target": {"path": "{tech_doc}"},
            "remediation_target": {"path": "{tech_doc}"},
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
        data = _feature_product_corpus()
        with pytest.raises(ValueError, match="unbound placeholder"):
            expand_corpus(data, {"tech_doc": "/abs/tech-doc.md"})


class TestHelpers:
    def test_corpus_ref(self):
        data = _feature_product_corpus()
        assert corpus_ref(data) == COMPOSED_CORPUS_REF

    def test_dispatch_ids(self):
        data = _feature_tech_corpus()
        assert dispatch_ids(data) == ["codebase-consistency", "solution-quality"]

    def test_resolve_dim_id_legacy_alias(self):
        data = _feature_product_corpus()
        assert resolve_dim_id(data, "e2") == "codebase-consistency"
        assert resolve_dim_id(data, "codebase-consistency") == "codebase-consistency"

    def test_resolve_unknown_dim(self):
        data = _feature_product_corpus()
        with pytest.raises(ValueError, match="unknown dimension"):
            resolve_dim_id(data, "e9")
