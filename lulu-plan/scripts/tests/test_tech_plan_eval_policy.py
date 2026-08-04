#!/usr/bin/env python3
"""Tests for tech_plan_eval_policy.py."""

import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_SCRIPTS_ROOT / "eval"))

from tech_plan_eval_policy import (
    require_feature_eval,
    select_dimension_defs,
    select_dimension_ids,
)

_TECH_PLAN = _SCRIPTS_ROOT.parent
_DIMENSION_DEFS = _TECH_PLAN / "dimension-defs"


class TestTechPlanEvalPolicy:
    def test_no_tech_upstream_returns_base_dimensions(self):
        assert select_dimension_ids() == [
            "codebase-consistency",
            "solution-quality",
        ]

    def test_tech_design_upstream_adds_tech_conformance(self):
        assert select_dimension_ids(tech_design_ref="/d.md") == [
            "codebase-consistency",
            "solution-quality",
            "tech-conformance",
        ]

    def test_tech_diagnostic_upstream_adds_tech_conformance(self):
        assert select_dimension_ids(tech_diagnostic_ref="/decision.md") == [
            "codebase-consistency",
            "solution-quality",
            "tech-conformance",
        ]

    def test_both_tech_upstreams_present_adds_tech_conformance_once(self):
        assert select_dimension_ids(
            tech_design_ref="/d.md", tech_diagnostic_ref="/decision.md"
        ) == [
            "codebase-consistency",
            "solution-quality",
            "tech-conformance",
        ]

    def test_require_feature_eval_topic_blocks(self):
        with pytest.raises(ValueError, match="topic cycles do not evaluate in lulu-plan"):
            require_feature_eval("topic")

    def test_select_dimension_defs_no_upstream(self):
        defs = select_dimension_defs(
            cycle_type="feature",
            dimension_defs_dir=_DIMENSION_DEFS,
        )
        assert [d["id"] for d in defs] == [
            "codebase-consistency",
            "solution-quality",
        ]

    def test_select_dimension_defs_with_tech_design_upstream(self):
        defs = select_dimension_defs(
            cycle_type="feature",
            dimension_defs_dir=_DIMENSION_DEFS,
            tech_design_ref="/d.md",
        )
        assert [d["id"] for d in defs] == [
            "codebase-consistency",
            "solution-quality",
            "tech-conformance",
        ]

    def test_select_dimension_defs_with_tech_diagnostic_upstream(self):
        defs = select_dimension_defs(
            cycle_type="feature",
            dimension_defs_dir=_DIMENSION_DEFS,
            tech_diagnostic_ref="/decision.md",
        )
        assert [d["id"] for d in defs] == [
            "codebase-consistency",
            "solution-quality",
            "tech-conformance",
        ]

    def test_select_dimension_defs_topic_blocks(self):
        with pytest.raises(ValueError, match="topic cycles do not evaluate in lulu-plan"):
            select_dimension_defs(
                cycle_type="topic",
                dimension_defs_dir=_DIMENSION_DEFS,
            )
