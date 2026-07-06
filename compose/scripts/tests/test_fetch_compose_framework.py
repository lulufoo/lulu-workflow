#!/usr/bin/env python3
"""Tests for fetch_compose_framework.py."""

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from fetch_compose_framework import (  # noqa: E402
    FetchComposeFrameworkError,
    fetch_compose_framework,
)
from compose_template_registry import resolve_config_key, scheme_template_keys  # noqa: E402


class TestResolveConfigKey:
    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            ("section-kw-criteria", "tpt_section_kw_criteria_url"),
            ("section-registry", "tpt_section_registry_url"),
            ("section-form-registry", "tpt_section_form_registry_url"),
            ("outline-registry", "tpt_outline_registry_url"),
            ("role-instance", "tpt_feature_role_instance_url"),
            ("domain-instance", "tpt_feature_domain_instance_url"),
        ],
    )
    def test_resolve_config_key(self, role: str, expected: str) -> None:
        assert resolve_config_key(role) == expected

    def test_resolve_config_key_tech_design(self) -> None:
        assert resolve_config_key("outline-registry", "lulu-design") == "tdt_outline_registry_url"
        assert resolve_config_key("section-registry", "lulu-design") == "tdt_section_registry_url"
        from compose_template_registry import ComposeTemplateError

        with pytest.raises(ComposeTemplateError, match="Invalid compose template role"):
            resolve_config_key("intent-eval-framework")

    def test_resolve_config_key_product_spec(self) -> None:
        assert resolve_config_key("section-form-registry", "lulu-spec") == (
            "pst_section_form_registry_url"
        )
        assert resolve_config_key("outline-registry", "lulu-spec") == "pst_outline_registry_url"
        assert resolve_config_key("inductive-scan-criteria", "lulu-spec") == (
            "pst_inductive_scan_criteria_url"
        )

    def test_scheme_keys(self) -> None:
        assert scheme_template_keys() == frozenset(
            {
                "domain-instance",
                "inductive-scan-criteria",
                "outline-registry",
                "role-instance",
                "section-form-registry",
                "section-kw-criteria",
                "section-registry",
            }
        )


class TestFetchComposeFramework:
    def test_fetch_product_spec_inductive_scan_criteria(self, tmp_path: Path) -> None:
        import fetch_compose_framework as mod

        root = Path(__file__).resolve().parents[4]
        content = mod.fetch_compose_framework(
            "inductive-scan-criteria",
            root,
            profile_id="lulu-spec",
        )
        data = __import__("json").loads(content)
        assert data["profile_id"] == "lulu-spec"
        assert data["expose_axis"]["coverage_sections"] == [
            "RN",
            "UR",
            "SN",
            "FL",
            "NG",
            "AC",
        ]
        assert data["shape_extraction"]["peeled_from_gate3"] == [
            "PB",
            "GO",
            "SC",
            "IO",
        ]
        assert "trigger_gap" in data["expose_axis"]["methods"]
        assert "exclusion_gap" in data["expose_axis"]["methods"]
        assert "io_instantiate_gap" in data["deferred"]["methods"]
        assert len(data["expose_axis"]["coverage_sections"]) == 6

    def test_fetch_tech_design_outline_registry(self, tmp_path: Path) -> None:
        import fetch_compose_framework as mod

        root = Path(__file__).resolve().parents[4]
        content = mod.fetch_compose_framework(
            "outline-registry",
            root,
            profile_id="lulu-design",
        )
        data = __import__("json").loads(content)
        assert data["outline_order"] == ["SI", "BD", "SH", "RS", "CT", "RD"]
        assert data["blocks"]["SH"]["intents"] == ["ST"]

    def test_delegates_to_fetch_template(self, tmp_path: Path) -> None:
        calls: list[tuple[str, str]] = []

        def stub_fetch(section: str, key: str, project_root: Path, **kwargs) -> str:
            calls.append((section, key))
            assert project_root == tmp_path.resolve()
            return f"# {section}.{key}\n"

        import fetch_compose_framework as mod

        original = mod.fetch_template
        mod.fetch_template = stub_fetch
        try:
            content = fetch_compose_framework("section-registry", tmp_path)
        finally:
            mod.fetch_template = original

        assert content == "# lulu-plan.tpt_section_registry_url\n"
        assert calls == [("lulu-plan", "tpt_section_registry_url")]

    def test_wraps_fetch_template_error(self, tmp_path: Path) -> None:
        import fetch_compose_framework as mod

        def fail_fetch(*_args, **_kwargs) -> str:
            from fetch_template import FetchTemplateError

            raise FetchTemplateError("network failed")

        original = mod.fetch_template
        mod.fetch_template = fail_fetch
        try:
            with pytest.raises(FetchComposeFrameworkError, match="network failed"):
                fetch_compose_framework("section-registry", tmp_path)
        finally:
            mod.fetch_template = original


class TestMainCli:
    def test_main_accepts_section_registry_role(self, tmp_path: Path, monkeypatch) -> None:
        import fetch_compose_framework as mod

        def stub_fetch(role: str, project_root: Path, **kwargs) -> str:
            assert role == "section-registry"
            return '{"version":"1"}\n'

        monkeypatch.setattr(mod, "fetch_compose_framework", stub_fetch)
        assert mod.main(["--role", "section-registry", "--project-root", str(tmp_path)]) == 0
