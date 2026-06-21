#!/usr/bin/env python3
"""Tests for transition_table.py — stage SSOT from transition-table.json."""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


class TestKnownStages:
    def test_topic_excludes_execution_stages(self):
        from transition_table import known_stages

        stages = known_stages("topic")
        assert "product-arch" in stages
        assert "tech-arch" in stages
        assert "tech-work-order" not in stages
        assert "tech-code" not in stages
        assert "tech-design" not in stages
        assert "tech-plan" not in stages

    def test_feature_includes_execution_stages(self):
        from transition_table import known_stages

        stages = known_stages("feature")
        assert "tech-design" in stages
        assert "tech-work-order" in stages
        assert "tech-code" in stages

    def test_allowed_stages_includes_diagnostic_legacy(self):
        from transition_table import allowed_stages

        assert "diagnostic" in allowed_stages("topic")
        assert "diagnostic" in allowed_stages("feature")
        from transition_table import known_stages

        assert "diagnostic" not in known_stages("feature")

    def test_known_stages_match_non_null_from_keys(self):
        from transition_table import known_stages, load_transitions

        for cycle_type in ("topic", "feature"):
            transitions = load_transitions(cycle_type)
            expected = {k for k in transitions if k is not None}
            assert known_stages(cycle_type) == frozenset(expected)
