#!/usr/bin/env python3
"""Tests for product_spec_eval_policy.py."""

import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS_ROOT / "eval"))

from product_spec_eval_policy import (  # noqa: E402
    product_eval_config_key,
    require_feature_eval,
    select_dimension_defs,
    select_dimension_ids,
)

_PRODUCT_SPEC = _SCRIPTS_ROOT.parent
_DIMENSION_DEFS = _PRODUCT_SPEC / "dimension-defs"


class TestProductSpecEvalPolicy:
    def test_select_dimension_ids(self):
        assert select_dimension_ids() == ["product-doc-quality"]

    def test_product_eval_config_key(self):
        assert product_eval_config_key("feature") == "pst_product_eval_framework_url"

    def test_require_feature_eval_topic_blocks(self):
        with pytest.raises(ValueError, match="topic cycles do not evaluate in lulu-spec"):
            require_feature_eval("topic")

    def test_select_dimension_defs_feature(self):
        defs = select_dimension_defs(
            cycle_type="feature",
            dimension_defs_dir=_DIMENSION_DEFS,
        )
        assert [d["id"] for d in defs] == ["product-doc-quality"]
        assert defs[0]["eval_target"]["path"] == "{eval_target_path}"

    def test_select_dimension_defs_topic_blocks(self):
        with pytest.raises(ValueError, match="topic cycles do not evaluate in lulu-spec"):
            select_dimension_defs(
                cycle_type="topic",
                dimension_defs_dir=_DIMENSION_DEFS,
            )
