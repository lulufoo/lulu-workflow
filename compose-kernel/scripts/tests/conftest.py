"""Pytest hooks: seed tech-plan template caches under tmp project_root/.cache."""

from __future__ import annotations

from pathlib import Path

import pytest

import bootstrap  # noqa: F401
from test_template_data import seed_tech_plan_test_caches  # noqa: WPS433


@pytest.fixture(scope="session")
def project_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session project root with tech-plan template caches (pytest temp dir)."""
    root = tmp_path_factory.mktemp("project")
    seed_tech_plan_test_caches(root)
    return root


@pytest.fixture(autouse=True)
def _use_project_template_cache(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve fetched templates via project_root (matches production cache layout)."""
    from compose_profile_context import reset_active_profile  # noqa: WPS433

    reset_active_profile()
    import section_registry_schema  # noqa: WPS433

    section_registry_schema._registry_for_path.cache_clear()
    monkeypatch.chdir(project_root)
