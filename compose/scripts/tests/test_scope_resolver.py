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
    resolve_inductive_slice,
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

    def test_topic_cycle_rejected(self):
        with pytest.raises(ScopeResolverError, match="invalid cycle_type"):
            resolve_role_markdown(cycle_id="topic-demo")

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
        assert "executable next steps" in md

    def test_topic_cycle_rejected(self):
        with pytest.raises(ScopeResolverError, match="invalid cycle_type"):
            resolve_domain_markdown(cycle_id="topic-demo")

    def test_domain_paths(self):
        root = Path.cwd()
        assert domain_instance_path(project_root=root).exists()

    def test_requires_cycle(self):
        with pytest.raises(ScopeResolverError, match="requires"):
            resolve_domain_markdown()


class TestResolveInductive:
    def test_prefers_json_over_md(self, tmp_path: Path):
        d = tmp_path / "inductive-scope"
        d.mkdir()
        (d / "ST.json").write_text(
            json.dumps(
                {
                    "key": "ST",
                    "status": "cleared",
                    "frontier_kw": 3,
                    "decisions": [
                        {
                            "id": "ST-d1",
                            "kw": 1,
                            "text": "hello",
                            "trigger": "seed",
                            "means": "scope",
                            "confidence": "direct",
                        }
                    ],
                    "open": [],
                    "deferred": [],
                }
            ),
            encoding="utf-8",
        )
        (d / "ST.md").write_text("# legacy\n", encoding="utf-8")
        path = resolve_inductive_slice("ST", d)
        assert path is not None
        assert path.endswith("ST.json")

    def test_falls_back_to_md(self, tmp_path: Path):
        d = tmp_path / "inductive-scope"
        d.mkdir()
        (d / "IF.md").write_text("# IF\n", encoding="utf-8")
        path = resolve_inductive_slice("IF", d)
        assert path is not None
        assert path.endswith("IF.md")

    def test_missing_returns_none(self, tmp_path: Path):
        assert resolve_inductive_slice("ST", tmp_path / "missing") is None
        assert resolve_inductive_slice("ST", None) is None
