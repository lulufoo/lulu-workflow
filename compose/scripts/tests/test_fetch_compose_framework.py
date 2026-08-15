#!/usr/bin/env python3
"""Tests for fetch_compose_framework.py."""

import json
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
from compose_template_registry import resolve_template_ref, scheme_template_keys  # noqa: E402


class TestResolveTemplateRef:
    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            (
                "section-kw-criteria",
                "lulu-dev-workflow/lulu-plan/templates/section-kw-criteria.md",
            ),
            (
                "section-registry",
                "lulu-dev-workflow/lulu-plan/templates/section-registry.json",
            ),
            (
                "section-form-registry",
                "lulu-dev-workflow/lulu-plan/templates/section-form-registry.json",
            ),
            (
                "role-instance",
                "lulu-dev-workflow/lulu-plan/templates/role-instance.json",
            ),
            (
                "domain-instance",
                "lulu-dev-workflow/lulu-plan/templates/domain-instance.json",
            ),
        ],
    )
    def test_resolve_template_ref(self, role: str, expected: str) -> None:
        assert resolve_template_ref(role) == expected

    def test_resolve_template_ref_tech_design(self) -> None:
        assert resolve_template_ref("section-registry", "lulu-design") == (
            "lulu-dev-workflow/lulu-design/templates/section-registry.json"
        )
        from compose_template_registry import ComposeTemplateError

        with pytest.raises(ComposeTemplateError, match="Invalid compose template role"):
            resolve_template_ref("intent-eval-framework")

    def test_resolve_template_ref_product_spec(self) -> None:
        assert resolve_template_ref("section-form-registry", "lulu-spec") == (
            "lulu-dev-workflow/lulu-spec/templates/section-form-registry.json"
        )
        assert resolve_template_ref("inductive-scan-criteria", "lulu-spec") == (
            "lulu-dev-workflow/lulu-spec/templates/inductive-scan-criteria.json"
        )

    def test_scheme_keys(self) -> None:
        assert scheme_template_keys() == frozenset(
            {
                "domain-instance",
                "inductive-scan-criteria",
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

    def test_delegates_to_fetch_template(self, tmp_path: Path) -> None:
        calls: list[tuple[str, str]] = []

        def stub_fetch(
            template_ref: str,
            project_root: Path,
            **kwargs,
        ) -> str:
            calls.append((kwargs["stage"], template_ref))
            assert project_root == tmp_path.resolve()
            return f"# {kwargs['stage']}.{template_ref}\n"

        import fetch_compose_framework as mod

        original = mod.fetch_template_ref
        mod.fetch_template_ref = stub_fetch
        try:
            content = fetch_compose_framework("section-registry", tmp_path, profile_id="lulu-plan")
        finally:
            mod.fetch_template_ref = original

        assert (
            content
            == "# lulu-plan.lulu-dev-workflow/lulu-plan/templates/section-registry.json\n"
        )
        assert calls == [
            (
                "lulu-plan",
                "lulu-dev-workflow/lulu-plan/templates/section-registry.json",
            )
        ]

    def test_wraps_fetch_template_error(self, tmp_path: Path) -> None:
        import fetch_compose_framework as mod

        def fail_fetch(*_args, **_kwargs) -> str:
            from fetch_template import FetchTemplateError

            raise FetchTemplateError("network failed")

        original = mod.fetch_template_ref
        mod.fetch_template_ref = fail_fetch
        try:
            with pytest.raises(FetchComposeFrameworkError, match="network failed"):
                fetch_compose_framework("section-registry", tmp_path, profile_id="lulu-plan")
        finally:
            mod.fetch_template_ref = original

    def test_legacy_runtime_profile_uses_old_cache_without_config(
        self,
        tmp_path: Path,
    ) -> None:
        profile = json.loads(
            (
                Path(__file__).resolve().parents[3]
                / "lulu-plan"
                / "compose-profile.json"
            ).read_text(encoding="utf-8")
        )
        profile["framework_templates"]["section-registry"] = "tpt_section_registry_url"
        profile_path = tmp_path / "runtime-profile.json"
        profile_path.write_text(json.dumps(profile), encoding="utf-8")

        from fetch_template import cache_path

        cached = cache_path(
            tmp_path,
            "cursor",
            "lulu-plan",
            "tpt_section_registry_url",
        )
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text("legacy cached template\n", encoding="utf-8")

        assert fetch_compose_framework(
            "section-registry",
            tmp_path,
            profile_path=profile_path,
            platform="cursor",
        ) == "legacy cached template\n"


class TestMainCli:
    def test_main_accepts_section_registry_role(self, tmp_path: Path, monkeypatch) -> None:
        import fetch_compose_framework as mod
        from workflow_paths import (  # noqa: WPS433
            DEFAULT_COMPOSE_PROFILE_ID,
            write_active_profile,
        )

        write_active_profile(tmp_path, "c1", DEFAULT_COMPOSE_PROFILE_ID)

        def stub_fetch(role: str, project_root: Path, **kwargs) -> str:
            assert role == "section-registry"
            return '{"version":"1"}\n'

        monkeypatch.setattr(mod, "fetch_compose_framework", stub_fetch)
        assert (
            mod.main(
                [
                    "--role",
                    "section-registry",
                    "--project-root",
                    str(tmp_path),
                    "--cycle-id",
                    "c1",
                ]
            )
            == 0
        )

    def test_library_rejects_missing_profile_id(self, tmp_path: Path) -> None:
        with pytest.raises(FetchComposeFrameworkError, match="profile_id required"):
            fetch_compose_framework("section-registry", tmp_path)

    def test_profile_path_wins_over_cycle_active_profile(self, tmp_path: Path) -> None:
        from workflow_paths import compose_profile_path, write_active_profile

        write_active_profile(tmp_path, "c1", "lulu-plan")
        calls: list[tuple[str, str]] = []

        def stub_fetch(
            template_ref: str,
            project_root: Path,
            **kwargs,
        ) -> str:
            calls.append((kwargs["stage"], template_ref))
            assert project_root == tmp_path.resolve()
            return f"# {kwargs['stage']}.{template_ref}\n"

        import fetch_compose_framework as mod

        original = mod.fetch_template_ref
        mod.fetch_template_ref = stub_fetch
        try:
            content = fetch_compose_framework(
                "section-registry",
                tmp_path,
                profile_id="lulu-plan",
                cycle_id="c1",
                profile_path=compose_profile_path("lulu-design"),
            )
        finally:
            mod.fetch_template_ref = original

        assert (
            content
            == "# lulu-design.lulu-dev-workflow/lulu-design/templates/section-registry.json\n"
        )
        assert calls == [
            (
                "lulu-design",
                "lulu-dev-workflow/lulu-design/templates/section-registry.json",
            )
        ]
