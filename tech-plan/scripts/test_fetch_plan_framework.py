#!/usr/bin/env python3
"""Tests for fetch_plan_framework.py."""

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from fetch_plan_framework import (  # noqa: E402
    FEATURE_ROLE_KEYS,
    TOPIC_ROLE_KEYS,
    FetchPlanFrameworkError,
    fetch_plan_framework,
    resolve_key,
)


class TestResolveKey:
    @pytest.mark.parametrize(
        ("cycle_type", "role", "expected"),
        [
            ("feature", "draft-template", "tpt_v2_url"),
            ("feature", "draft-meta", "tpt_meta_v2_url"),
            ("feature", "eval-ptc", "ptc_url"),
            ("feature", "eval-tpef", "tpef_url"),
            ("topic", "draft-template", "shaping_tpt_url"),
            ("topic", "draft-meta", "tpt_meta_url"),
            ("topic", "eval-ptc", "ptc_url"),
            ("topic", "eval-tpef", "shaping_tpef_url"),
        ],
    )
    def test_resolve_key(self, cycle_type: str, role: str, expected: str) -> None:
        assert resolve_key(cycle_type, role) == expected

    def test_feature_and_topic_maps_have_same_roles(self) -> None:
        assert set(FEATURE_ROLE_KEYS) == set(TOPIC_ROLE_KEYS)

    def test_invalid_cycle_type(self) -> None:
        with pytest.raises(FetchPlanFrameworkError, match="Invalid cycle_type"):
            resolve_key("invalid", "draft-meta")

    def test_invalid_role(self) -> None:
        with pytest.raises(FetchPlanFrameworkError, match="Invalid role"):
            resolve_key("feature", "unknown-role")


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
            content = fetch_plan_framework("topic", "eval-tpef", tmp_path)
        finally:
            mod.fetch_template = original

        assert content == "# tech-plan.shaping_tpef_url\n"
        assert calls == [("tech-plan", "shaping_tpef_url")]

    def test_wraps_fetch_template_error(self, tmp_path: Path) -> None:
        import fetch_plan_framework as mod

        def fail_fetch(*_args, **_kwargs) -> str:
            from fetch_template import FetchTemplateError

            raise FetchTemplateError("network failed")

        original = mod.fetch_template
        mod.fetch_template = fail_fetch
        try:
            with pytest.raises(FetchPlanFrameworkError, match="network failed"):
                fetch_plan_framework("feature", "draft-meta", tmp_path)
        finally:
            mod.fetch_template = original
