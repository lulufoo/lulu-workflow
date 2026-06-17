#!/usr/bin/env python3
"""Tests for tech_plan_eval_policy.py."""

import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS_ROOT / "eval"))

from tech_plan_eval_policy import (
    intent_eval_config_key,
    require_feature_eval,
    select_dimension_defs,
    select_dimension_ids,
)

_TECH_PLAN = _SCRIPTS_ROOT.parent
_DIMENSION_DEFS = _TECH_PLAN / "dimension-defs"


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

    def test_require_feature_eval_topic_blocks(self):
        with pytest.raises(ValueError, match="topic cycles do not evaluate in tech-plan"):
            require_feature_eval("topic")

    def test_select_dimension_defs_feature(self):
        defs = select_dimension_defs(
            product_ref="",
            mode="tech",
            cycle_type="feature",
            dimension_defs_dir=_DIMENSION_DEFS,
        )
        assert [d["id"] for d in defs] == [
            "codebase-consistency",
            "solution-quality",
        ]

    def test_select_dimension_defs_topic_blocks(self):
        with pytest.raises(ValueError, match="topic cycles do not evaluate in tech-plan"):
            select_dimension_defs(
                product_ref="",
                mode="tech",
                cycle_type="topic",
                dimension_defs_dir=_DIMENSION_DEFS,
            )
