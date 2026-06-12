#!/usr/bin/env python3
"""Tests for plan_scope.py and plan_scope_schema.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from plan_scope import PlanScopeError, resolve_role_markdown, resolve_role_summary  # noqa: E402
from plan_scope_schema import default_roles_path, load_roles, validate_roles  # noqa: E402


class TestValidateRoles:
    def test_default_roles_valid(self):
        data = load_roles(default_roles_path())
        assert validate_roles(data) == []

    def test_missing_scope(self):
        data = load_roles(default_roles_path())
        scopes = dict(data["scopes"])
        del scopes["topic"]
        bad = {**data, "scopes": scopes}
        assert any("scopes.topic" in err for err in validate_roles(bad))


class TestResolveRole:
    def test_topic_by_cycle_type(self):
        md = resolve_role_markdown(cycle_type="topic")
        assert "## Plan Scope Constraints" in md
        assert "cycle_type: topic" in md
        assert "### Role" in md
        assert "architect" in md.lower()

    def test_feature_by_cycle_id(self):
        md = resolve_role_markdown(cycle_id="feat-demo")
        assert "cycle_type: feature" in md
        assert "technical expert" in md.lower()

    def test_topic_by_cycle_id(self):
        md = resolve_role_markdown(cycle_id="topic-demo")
        assert "cycle_type: topic" in md

    def test_summary(self):
        summary = resolve_role_summary(cycle_type="feature")
        assert summary == "feature"

    def test_requires_scope_or_cycle(self):
        with pytest.raises(PlanScopeError, match="requires"):
            resolve_role_markdown()
