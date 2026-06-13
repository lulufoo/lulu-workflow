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
            ("draft-meta", "tpt_draft_meta_url"),
            ("layer-standards", "tpt_layer_standards_url"),
            ("layer-diagnostic", "tpef_url"),
            ("eval-ptc", "ptc_url"),
        ],
    )
    def test_resolve_key(self, role: str, expected: str) -> None:
        assert resolve_key(role) == expected

    def test_invalid_role(self) -> None:
        with pytest.raises(FetchPlanFrameworkError, match="Invalid role"):
            resolve_key("unknown-role")

    def test_all_roles_mapped(self) -> None:
        assert set(ROLE_KEYS) == {
            "draft-meta",
            "layer-standards",
            "layer-diagnostic",
            "eval-ptc",
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
            content = fetch_plan_framework("layer-diagnostic", tmp_path)
        finally:
            mod.fetch_template = original

        assert content == "# tech-plan.tpef_url\n"
        assert calls == [("tech-plan", "tpef_url")]

    def test_wraps_fetch_template_error(self, tmp_path: Path) -> None:
        import fetch_plan_framework as mod

        def fail_fetch(*_args, **_kwargs) -> str:
            from fetch_template import FetchTemplateError

            raise FetchTemplateError("network failed")

        original = mod.fetch_template
        mod.fetch_template = fail_fetch
        try:
            with pytest.raises(FetchPlanFrameworkError, match="network failed"):
                fetch_plan_framework("draft-meta", tmp_path)
        finally:
            mod.fetch_template = original


class TestMainCli:
    def test_main_accepts_role_without_cycle_type(self, tmp_path: Path, monkeypatch) -> None:
        import fetch_plan_framework as mod

        def stub_fetch(role: str, project_root: Path, **kwargs) -> str:
            assert role == "layer-diagnostic"
            return "# diagnostic\n"

        monkeypatch.setattr(mod, "fetch_plan_framework", stub_fetch)
        assert mod.main(["--role", "layer-diagnostic", "--project-root", str(tmp_path)]) == 0
