#!/usr/bin/env python3
"""Tests for transition_table.py — stage SSOT from transition-table.json."""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


class TestNextStepsForStage:
    def test_product_diagnostic_feature(self):
        from transition_table import next_steps_for_stage

        assert next_steps_for_stage("lulu-bet", "feature") == ["lulu-spec"]

    def test_product_diagnostic_topic_has_no_next_step(self):
        from transition_table import next_steps_for_stage

        assert next_steps_for_stage("lulu-bet", "topic") == []

    def test_tech_diagnostic_feature(self):
        from transition_table import next_steps_for_stage

        assert next_steps_for_stage("lulu-approach", "feature") == [
            "lulu-design",
            "lulu-plan",
            "lulu-tasks",
        ]

    def test_terminal_stage(self):
        from transition_table import next_steps_for_stage

        assert next_steps_for_stage("lulu-approach", "topic") == []


class TestKnownStages:
    def test_topic_excludes_execution_stages(self):
        from transition_table import allowed_stages

        stages = allowed_stages("topic")
        assert "lulu-blueprint" not in stages
        assert "lulu-arch" not in stages
        assert "lulu-tasks" not in stages
        assert "lulu-exec" not in stages
        assert "lulu-design" not in stages
        assert "lulu-plan" not in stages

    def test_feature_includes_execution_stages(self):
        from transition_table import known_stages

        stages = known_stages("feature")
        assert "lulu-design" in stages
        assert "lulu-tasks" in stages
        assert "lulu-exec" in stages

    def test_allowed_stages_includes_decision(self):
        from transition_table import allowed_stages

        assert "decision" in allowed_stages("topic")
        assert "decision" in allowed_stages("feature")
        from transition_table import known_stages

        assert "decision" not in known_stages("feature")

    def test_known_stages_match_non_null_from_keys(self):
        from transition_table import known_stages, load_transitions

        for cycle_type in ("topic", "feature"):
            transitions = load_transitions(cycle_type)
            expected = {k for k in transitions if k is not None}
            assert known_stages(cycle_type) == frozenset(expected)

    def test_allowed_stages_cover_every_named_stage(self):
        from transition_table import allowed_stages, load_transitions

        for cycle_type in ("topic", "feature"):
            transitions = load_transitions(cycle_type)
            named = {k for k in transitions if k is not None}.union(*transitions.values())
            assert allowed_stages(cycle_type) == frozenset(named) | {"decision"}

    def test_feature_allowed_stages_are_its_known_stages(self):
        from transition_table import allowed_stages, known_stages

        assert allowed_stages("feature") == known_stages("feature") | {"decision"}
