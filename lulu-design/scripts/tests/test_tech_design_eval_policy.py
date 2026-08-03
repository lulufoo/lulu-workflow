#!/usr/bin/env python3
"""Tests for tech_design_eval_policy.py."""

import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS_ROOT / "eval"))

from tech_design_eval_policy import (  # noqa: E402
    design_quality_config_key,
    require_feature_eval,
    select_dimension_defs,
    select_dimension_ids,
)

_TECH_DESIGN = _SCRIPTS_ROOT.parent
_DIMENSION_DEFS = _TECH_DESIGN / "dimension-defs"


class TestTechDesignEvalPolicy:
    def test_select_dimension_ids_tech_mode(self):
        assert select_dimension_ids() == [
            "codebase-consistency",
            "solution-quality",
        ]

    def test_select_dimension_ids_product_mode_no_ref(self):
        assert select_dimension_ids(mode="product", upstream_baseline_ref="") == [
            "codebase-consistency",
            "solution-quality",
        ]

    def test_select_dimension_ids_product_mode_with_ref(self):
        assert select_dimension_ids(mode="product", upstream_baseline_ref="/p.md") == [
            "codebase-consistency",
            "solution-quality",
            "intent-alignment",
        ]

    def test_design_quality_config_key(self):
        assert design_quality_config_key("feature") == "tdt_design_quality_framework_url"

    def test_require_feature_eval_topic_blocks(self):
        with pytest.raises(ValueError, match="topic cycles do not evaluate in lulu-design"):
            require_feature_eval("topic")

    def test_select_dimension_defs_feature_tech(self):
        defs = select_dimension_defs(
            cycle_type="feature",
            dimension_defs_dir=_DIMENSION_DEFS,
        )
        assert [d["id"] for d in defs] == [
            "codebase-consistency",
            "solution-quality",
        ]
        assert defs[0]["eval_target"]["path"] == "{eval_target_path}"

    def test_select_dimension_defs_feature_product(self):
        defs = select_dimension_defs(
            cycle_type="feature",
            dimension_defs_dir=_DIMENSION_DEFS,
            mode="product",
            upstream_baseline_ref="/p.md",
        )
        assert [d["id"] for d in defs] == [
            "codebase-consistency",
            "solution-quality",
            "intent-alignment",
        ]
        assert defs[2]["legacy_alias"] == "d3"

    def test_select_dimension_defs_topic_blocks(self):
        with pytest.raises(ValueError, match="topic cycles do not evaluate in lulu-design"):
            select_dimension_defs(
                cycle_type="topic",
                dimension_defs_dir=_DIMENSION_DEFS,
            )
