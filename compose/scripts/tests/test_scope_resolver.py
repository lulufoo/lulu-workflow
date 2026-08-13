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
        assert "consume_policy" in fields

    def test_plan_framework_role_consume_policy_valid(self):
        from framework_template_sources import tech_plan_feature_role_instance

        data = tech_plan_feature_role_instance()
        assert validate_role_instance(data) == []
        rules = data["consume_policy"]["rules"]
        assert [r["id"] for r in rules] == ["D-RISK", "D-SEAM", "D-DEC"]

    def test_consume_policy_rejects_empty_rules(self):
        data = load_and_validate_role_instance("feature")
        bad = {**data, "consume_policy": {"rules": []}}
        assert any("rules" in e for e in validate_role_instance(bad))


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

    def test_cognitive_framework_optional_absent(self):
        data = load_and_validate_role_instance("feature")
        without = {k: v for k, v in data.items() if k != "cognitive_framework"}
        assert validate_role_instance(without) == []
        fields = get_role_fields(without)
        assert "cognitive_framework" not in fields
        assert "priority_tendency" in fields

    def test_cognitive_framework_empty_string_invalid(self):
        data = load_and_validate_role_instance("feature")
        bad = {**data, "cognitive_framework": "  "}
        assert any("cognitive_framework" in err for err in validate_role_instance(bad))

    def test_cognitive_framework_present_still_ok(self):
        data = load_and_validate_role_instance("feature")
        with_fw = {**data, "cognitive_framework": "legacy analysis dimensions"}
        assert validate_role_instance(with_fw) == []
        assert get_role_fields(with_fw)["cognitive_framework"] == (
            "legacy analysis dimensions"
        )


class TestResolveRole:
    def test_feature_by_cycle_type(self):
        md = resolve_role_markdown(cycle_type="feature")
        assert "## Scope Constraints" in md
        assert "cycle_type: feature" in md
        assert "### Role Instance" in md
        assert "technical expert" in md.lower()
        assert '"role_prompt"' in md
        assert "### Role Fields" not in md

    def test_feature_by_cycle_id(self):
        md = resolve_role_markdown(cycle_id="feat-demo")
        assert "cycle_type: feature" in md
        payload = md.split("### Role Instance")[1]
        assert "technical_expert" in payload
        assert '"role_prompt"' in payload

    def test_topic_with_lulu_arch_succeeds(self):
        md = resolve_role_markdown(cycle_id="topic-demo", profile_id="lulu-arch")
        assert "## Scope Constraints" in md
        assert "cycle_type: topic" in md
        assert "### Role Instance" in md
        assert "system architect" in md.lower()
        payload = md.split("### Role Instance")[1]
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
        assert "## Scope Constraints" in md
        assert "### Domain Instance" in md
        assert "cycle_type: feature" in md
        assert "tech_plan_feature" in md
        assert "Technical execution planning" in md

    def test_topic_with_lulu_arch_succeeds(self):
        md = resolve_domain_markdown(cycle_id="topic-demo", profile_id="lulu-arch")
        assert "## Scope Constraints" in md
        assert "### Domain Instance" in md
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


class TestScopeResolverCli:
    def test_resolve_role_cycle_type(self, capsys):
        from scope_resolver import main

        assert (
            main(
                [
                    "resolve-role",
                    "--cycle-type",
                    "feature",
                    "--project-root",
                    ".",
                ],
            )
            == 0
        )
        out = capsys.readouterr().out
        assert "## Scope Constraints" in out
        assert "### Role Instance" in out
