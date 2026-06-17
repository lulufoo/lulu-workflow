#!/usr/bin/env python3
"""Tests for tech_plan_eval_policy.py."""

from pathlib import Path

import pytest

from tech_plan_eval_policy import (
    intent_eval_config_key,
    select_dimension_defs,
    select_dimension_ids,
    stamps_dir_for_cycle_type,
)

_TECH_PLAN = Path(__file__).resolve().parents[1]
_CORPORA = _TECH_PLAN / "corpora"
_FEATURE_STAMPS = _CORPORA / "stamps" / "feature"


class TestTechPlanEvalPolicy:
    def test_product_ref_includes_e1(self):
        assert select_dimension_ids(product_ref="/p.md", mode="tech") == [
            "intent-alignment",
            "codebase-consistency",
            "solution-quality",
        ]

    def test_tech_mode_without_product_ref(self):
        assert select_dimension_ids(product_ref="", mode="tech") == [
            "codebase-consistency",
            "solution-quality",
        ]

    def test_product_mode_without_product_ref_blocks(self):
        with pytest.raises(ValueError, match="product_ref is empty"):
            select_dimension_ids(product_ref="", mode="product")

    def test_intent_eval_config_key_is_shared(self):
        assert intent_eval_config_key("feature") == "tpt_intent_eval_framework_url"
        assert intent_eval_config_key("topic") == "tpt_intent_eval_framework_url"
        assert intent_eval_config_key("other") == "tpt_intent_eval_framework_url"

    def test_stamps_dir_feature(self):
        assert stamps_dir_for_cycle_type(_CORPORA, "feature") == _FEATURE_STAMPS

    def test_stamps_dir_topic_not_implemented(self):
        with pytest.raises(ValueError, match="topic eval stamps are not implemented"):
            stamps_dir_for_cycle_type(_CORPORA, "topic")

    def test_select_dimension_defs_feature(self):
        defs = select_dimension_defs(
            product_ref="",
            mode="tech",
            cycle_type="feature",
            corpora_dir=_CORPORA,
        )
        assert [d["id"] for d in defs] == [
            "codebase-consistency",
            "solution-quality",
        ]

    def test_select_dimension_defs_topic_blocks(self):
        with pytest.raises(ValueError, match="topic eval stamps are not implemented"):
            select_dimension_defs(
                product_ref="",
                mode="tech",
                cycle_type="topic",
                corpora_dir=_CORPORA,
            )
