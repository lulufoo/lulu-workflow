#!/usr/bin/env python3
"""Tests for scope_resolver.py and plan-scope schema modules."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scope_resolver import (  # noqa: E402
    ScopeResolverError,
    resolve_domain_markdown,
    resolve_role_markdown,
    resolve_role_summary,
)
from domain_instance_schema import domain_instance_path  # noqa: E402
from schema_common import validate_all_plan_scope_instances  # noqa: E402
from role_instance_schema import (  # noqa: E402
    get_role_fields,
    get_role_prompt,
    get_schema as get_role_schema,
    load_and_validate_role_instance,
    role_instance_path,
    validate_role_instance,
)


class TestRoleSchema:
    def test_get_schema_includes_role_prompt(self):
        fields = {entry["field"] for entry in get_role_schema()}
        assert "role_prompt" in fields
        assert "$schema_id" in fields


class TestValidateRoleInstances:
    def test_default_instances_valid(self):
        assert validate_all_plan_scope_instances() == []

    def test_missing_role_prompt(self):
        data = load_and_validate_role_instance("feature")
        bad = {**data, "role_prompt": ""}
        assert any("role_prompt" in err for err in validate_role_instance(bad))

    def test_cycle_type_mismatch(self):
        data = load_and_validate_role_instance("feature")
        errors = validate_role_instance(data, expected_cycle_type="topic")
        assert any("cycle_type mismatch" in err for err in errors)


class TestResolveRole:
    def test_feature_by_cycle_type(self):
        md = resolve_role_markdown(cycle_type="feature")
        assert "## Plan Scope Constraints" in md
        assert "cycle_type: feature" in md
        assert "### Role" in md
        assert "technical expert" in md.lower()
        assert "### Role Fields" in md
        assert "role_prompt" not in md

    def test_feature_by_cycle_id(self):
        md = resolve_role_markdown(cycle_id="feat-demo")
        assert "cycle_type: feature" in md
        payload = md.split("### Role Fields")[1]
        assert "technical_expert" in payload

    def test_topic_with_lulu_arch_succeeds(self):
        md = resolve_role_markdown(cycle_id="topic-demo", profile_id="lulu-arch")
        assert "## Plan Scope Constraints" in md
        assert "cycle_type: topic" in md
        assert "### Role" in md
        assert "system architect" in md.lower()
        payload = md.split("### Role Fields")[1]
        assert "system_architect" in payload

    def test_topic_with_feature_profile_mismatches(self):
        with pytest.raises(ScopeResolverError, match="cycle_type mismatch"):
            resolve_role_markdown(cycle_id="topic-demo", profile_id="lulu-plan")

    def test_role_fields_exclude_prompt(self):
        data = load_and_validate_role_instance("feature")
        fields = get_role_fields(data)
        assert "role_prompt" not in fields
        assert fields["role_id"] == "technical_expert"
        assert get_role_prompt(data).startswith("You are acting")

    def test_summary(self):
        summary = resolve_role_summary(cycle_type="feature")
        assert summary == "feature"

    def test_requires_scope_or_cycle(self):
        with pytest.raises(ScopeResolverError, match="requires"):
            resolve_role_markdown()

    def test_instance_paths(self):
        root = Path.cwd()
        assert role_instance_path(project_root=root).exists()


class TestResolveDomain:
    def test_feature_domain_by_cycle_type(self):
        md = resolve_domain_markdown(cycle_type="feature")
        assert "## Domain Instance" in md
        assert "cycle_type: feature" in md
        assert "tech_plan_feature" in md
        assert "execution readiness" in md

    def test_topic_with_lulu_arch_succeeds(self):
        md = resolve_domain_markdown(cycle_id="topic-demo", profile_id="lulu-arch")
        assert "## Domain Instance" in md
        assert "cycle_type: topic" in md
        assert "tech_arch_topic" in md

    def test_topic_with_feature_profile_mismatches(self):
        with pytest.raises(ScopeResolverError, match="cycle_type mismatch"):
            resolve_domain_markdown(cycle_id="topic-demo", profile_id="lulu-plan")

    def test_domain_paths(self):
        root = Path.cwd()
        assert domain_instance_path(project_root=root).exists()

    def test_requires_cycle(self):
        with pytest.raises(ScopeResolverError, match="requires"):
            resolve_domain_markdown()


class TestScopeResolverCliProfile:
    """--profile must work before and after the subcommand (Init macro friction fix)."""

    def test_profile_after_subcommand_accepted(self, capsys):
        from scope_resolver import main

        assert (
            main(
                [
                    "resolve-role",
                    "--cycle-type",
                    "feature",
                    "--project-root",
                    ".",
                    "--profile",
                    "lulu-plan",
                ],
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "## Plan Scope Constraints" in out

    def test_profile_before_subcommand_accepted(self, capsys):
        from scope_resolver import main

        assert (
            main(
                [
                    "--profile",
                    "lulu-plan",
                    "--project-root",
                    ".",
                    "resolve-role",
                    "--cycle-type",
                    "feature",
                ],
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "## Plan Scope Constraints" in out
