#!/usr/bin/env python3
"""Tests for fetch_plan_framework.py."""

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from fetch_plan_framework import (  # noqa: E402
    ROLE_KEYS,
    FetchPlanFrameworkError,
    fetch_plan_framework,
    resolve_key,
)


class TestResolveKey:
    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            ("section-kw-criteria", "tpt_section_kw_criteria_url"),
            ("section-registry", "tpt_section_registry_url"),
            ("outline-registry", "tpt_outline_registry_url"),
            ("feature-role-instance", "tpt_feature_role_instance_url"),
            ("feature-domain-instance", "tpt_feature_domain_instance_url"),
            ("topic-role-instance", "tpt_topic_role_instance_url"),
            ("topic-domain-instance", "tpt_topic_domain_instance_url"),
            ("eval-ptc", "tpt_product_tech_spec_crosscheck_url"),
            ("intent-eval-framework", "tpt_intent_eval_framework_url"),
        ],
    )
    def test_resolve_key(self, role: str, expected: str) -> None:
        assert resolve_key(role) == expected

    def test_invalid_role(self) -> None:
        with pytest.raises(FetchPlanFrameworkError, match="Invalid role"):
            resolve_key("unknown-role")

    def test_decision_doc_mapping_role_removed(self) -> None:
        with pytest.raises(FetchPlanFrameworkError, match="Invalid role"):
            resolve_key("decision-doc-mapping")

    def test_all_roles_mapped(self) -> None:
        assert set(ROLE_KEYS) == {
            "eval-ptc",
            "feature-domain-instance",
            "feature-role-instance",
            "intent-eval-framework",
            "outline-registry",
            "section-kw-criteria",
            "section-registry",
            "topic-domain-instance",
            "topic-role-instance",
        }


class TestFetchPlanFramework:
    def test_delegates_to_fetch_template(self, tmp_path: Path) -> None:
        calls: list[tuple[str, str]] = []

        def stub_fetch(section: str, key: str, project_root: Path, **kwargs) -> str:
            calls.append((section, key))
            assert project_root == tmp_path.resolve()
            return f"# {section}.{key}\n"

        import fetch_plan_framework as mod

        original = mod.fetch_template
        mod.fetch_template = stub_fetch
        try:
            content = fetch_plan_framework("intent-eval-framework", tmp_path)
        finally:
            mod.fetch_template = original

        assert content == "# tech-plan.tpt_intent_eval_framework_url\n"
        assert calls == [("tech-plan", "tpt_intent_eval_framework_url")]

    def test_wraps_fetch_template_error(self, tmp_path: Path) -> None:
        import fetch_plan_framework as mod

        def fail_fetch(*_args, **_kwargs) -> str:
            from fetch_template import FetchTemplateError

            raise FetchTemplateError("network failed")

        original = mod.fetch_template
        mod.fetch_template = fail_fetch
        try:
            with pytest.raises(FetchPlanFrameworkError, match="network failed"):
                fetch_plan_framework("section-registry", tmp_path)
        finally:
            mod.fetch_template = original


class TestMainCli:
    def test_main_accepts_intent_eval_framework_role(self, tmp_path: Path, monkeypatch) -> None:
        import fetch_plan_framework as mod

        def stub_fetch(role: str, project_root: Path, **kwargs) -> str:
            assert role == "intent-eval-framework"
            return "# criteria\n"

        monkeypatch.setattr(mod, "fetch_plan_framework", stub_fetch)
        assert mod.main(["--role", "intent-eval-framework", "--project-root", str(tmp_path)]) == 0
