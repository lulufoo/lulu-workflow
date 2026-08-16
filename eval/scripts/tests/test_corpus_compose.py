#!/usr/bin/env python3
"""Tests for corpus_compose.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from corpus_compose import (  # noqa: E402
    compose_corpus,
    corpus_fingerprint,
    is_composed_corpus_ref,
    load_dimension_def,
)

_LULU_PLAN_COMPOSED_CORPUS_REF = "lulu-plan-composed@2"
_TECH_DESIGN_COMPOSED_CORPUS_REF = "lulu-design-composed@2"

_TECH_PLAN_DIMENSION_DEFS = Path(__file__).resolve().parents[3] / "lulu-plan" / "dimension-defs"
_TECH_DESIGN_DIMENSION_DEFS = Path(__file__).resolve().parents[3] / "lulu-design" / "dimension-defs"


class TestCorpusCompose:
    def test_fingerprint_stable(self):
        fp = corpus_fingerprint(
            ["intent-alignment", "codebase-consistency", "solution-quality"],
            cycle_type="feature",
        )
        assert len(fp) == 16
        assert fp == corpus_fingerprint(
            ["solution-quality", "intent-alignment", "codebase-consistency"],
            cycle_type="feature",
        )

    def test_fingerprint_includes_cycle_type(self):
        feature_fp = corpus_fingerprint(
            ["codebase-consistency", "solution-quality"],
            cycle_type="feature",
        )
        topic_fp = corpus_fingerprint(
            ["codebase-consistency", "solution-quality"],
            cycle_type="topic",
        )
        assert feature_fp != topic_fp

    def test_compose_tech_plan_session(self):
        dims = [
            load_dimension_def(_TECH_PLAN_DIMENSION_DEFS / "codebase-consistency.json"),
            load_dimension_def(_TECH_PLAN_DIMENSION_DEFS / "solution-quality.json"),
            load_dimension_def(_TECH_PLAN_DIMENSION_DEFS / "tech-conformance.json"),
        ]
        corpus = compose_corpus(
            corpus_id="lulu-plan-composed",
            corpus_version="2",
            scope="lulu-plan",
            dimensions=dims,
        )
        assert corpus["id"] == "lulu-plan-composed"
        assert is_composed_corpus_ref(_LULU_PLAN_COMPOSED_CORPUS_REF)
        assert is_composed_corpus_ref(_TECH_DESIGN_COMPOSED_CORPUS_REF)
        assert corpus["dimensions"][0]["review"]["seq"] == 1
        assert corpus["dimensions"][2]["review"]["output_path"] == "tech-review-e{M}3.md"

    def test_compose_rejects_empty(self):
        with pytest.raises(ValueError, match="non-empty"):
            compose_corpus(
                corpus_id="lulu-plan-composed",
                corpus_version="2",
                scope="lulu-plan",
                dimensions=[],
            )

    def test_compose_tech_design(self):
        dims = [
            load_dimension_def(_TECH_DESIGN_DIMENSION_DEFS / "codebase-consistency.json"),
            load_dimension_def(_TECH_DESIGN_DIMENSION_DEFS / "solution-quality.json"),
        ]
        corpus = compose_corpus(
            corpus_id="lulu-design-composed",
            corpus_version="2",
            scope="lulu-design",
            dimensions=dims,
            review_output_prefix="design-review",
        )
        assert corpus["id"] == "lulu-design-composed"
        assert corpus["dimensions"][1]["review"]["output_path"] == "design-review-e{M}2.md"

    def test_compose_tech_design_product_mode(self):
        dims = [
            load_dimension_def(_TECH_DESIGN_DIMENSION_DEFS / "codebase-consistency.json"),
            load_dimension_def(_TECH_DESIGN_DIMENSION_DEFS / "solution-quality.json"),
            load_dimension_def(_TECH_DESIGN_DIMENSION_DEFS / "intent-alignment.json"),
        ]
        corpus = compose_corpus(
            corpus_id="lulu-design-composed",
            corpus_version="2",
            scope="lulu-design",
            dimensions=dims,
            review_output_prefix="design-review",
        )
        assert len(corpus["dimensions"]) == 3
        assert corpus["dimensions"][2]["id"] == "intent-alignment"
        assert corpus["dimensions"][2]["review"]["output_path"] == "design-review-e{M}3.md"
        assert corpus["dimensions"][2]["review"]["seq"] == 3

    def test_is_composed_corpus_ref_matches_generic_pattern(self):
        assert is_composed_corpus_ref("lulu-arch-composed@1")
        assert not is_composed_corpus_ref("lulu-arch-composed")
        assert not is_composed_corpus_ref("static-corpus@1")
