#!/usr/bin/env python3
"""Tests for compose_template_loader.py."""

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from compose_template_registry import ComposeTemplateError, resolve_template_ref, scheme_template_keys  # noqa: E402
from compose_template_loader import (  # noqa: E402
    ComposeTemplateLoadError,
    load_compose_template,
    resolve_compose_template_path,
)
from workflow_paths import WORKFLOW_ROOT, compose_profile_path  # noqa: E402


class TestResolveTemplateRef:
    @pytest.mark.parametrize(
        ("role", "expected"),
        [
            (
                "section-kw-criteria",
                "lulu-workflow/lulu-plan/templates/section-kw-criteria.md",
            ),
            (
                "section-registry",
                "lulu-workflow/lulu-plan/templates/section-registry.json",
            ),
            (
                "section-form-registry",
                "lulu-workflow/lulu-plan/templates/section-form-registry.json",
            ),
            (
                "role-instance",
                "lulu-workflow/lulu-plan/templates/role-instance.json",
            ),
            (
                "domain-instance",
                "lulu-workflow/lulu-plan/templates/domain-instance.json",
            ),
        ],
    )
    def test_resolve_template_ref(self, role: str, expected: str) -> None:
        assert resolve_template_ref(role) == expected

    def test_resolve_template_ref_tech_design(self) -> None:
        assert resolve_template_ref("section-registry", "lulu-design") == (
            "lulu-workflow/lulu-design/templates/section-registry.json"
        )
        with pytest.raises(ComposeTemplateError, match="Invalid compose template role"):
            resolve_template_ref("intent-eval-framework")

    def test_resolve_template_ref_product_spec(self) -> None:
        assert resolve_template_ref("section-form-registry", "lulu-spec") == (
            "lulu-workflow/lulu-spec/templates/section-form-registry.json"
        )

    def test_scheme_keys(self) -> None:
        assert scheme_template_keys() == frozenset(
            {
                "domain-instance",
                "role-instance",
                "section-form-registry",
                "section-kw-criteria",
                "section-registry",
            }
        )


class TestLoadComposeTemplate:
    def test_loads_installed_lulu_plan(self, tmp_path: Path) -> None:
        content = load_compose_template(
            "section-registry", tmp_path, profile_id="lulu-plan"
        )
        data = json.loads(content)
        assert "CTX" in (data.get("sections") or {})

    def test_resolve_path_is_skill_file(self, tmp_path: Path) -> None:
        path = resolve_compose_template_path(
            "section-registry", tmp_path, profile_id="lulu-plan"
        )
        assert path == (
            WORKFLOW_ROOT / "lulu-plan" / "templates" / "section-registry.json"
        )
        assert path.is_file()

    def test_profile_path_wins_over_cycle_active_profile(self, tmp_path: Path) -> None:
        from workflow_paths import write_active_profile

        write_active_profile(tmp_path, "c1", "lulu-plan")
        content = load_compose_template(
            "section-registry",
            tmp_path,
            profile_id="lulu-plan",
            cycle_id="c1",
            profile_path=compose_profile_path("lulu-design"),
        )
        data = json.loads(content)
        assert "GOAL" in (data.get("section_order") or [])

    def test_library_rejects_missing_profile_id(self, tmp_path: Path) -> None:
        with pytest.raises(ComposeTemplateLoadError, match="profile_id required"):
            load_compose_template("section-registry", tmp_path)

    def test_rejects_non_skill_refs(self, tmp_path: Path) -> None:
        source = json.loads(compose_profile_path("lulu-plan").read_text(encoding="utf-8"))
        cases = (
            "file:///tmp/section-registry.json",
            "/tmp/section-registry.json",
            "https://github.com/example/repo/blob/main/section-registry.json",
            "tpt_section_registry_url",
        )
        for ref in cases:
            profile = dict(source)
            profile["framework_templates"] = dict(source["framework_templates"])
            profile["framework_templates"]["section-registry"] = ref
            profile_path = tmp_path / f"profile-{hash(ref)}.json"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            with pytest.raises(ComposeTemplateLoadError, match="lulu-workflow/"):
                load_compose_template(
                    "section-registry", tmp_path, profile_path=profile_path
                )
