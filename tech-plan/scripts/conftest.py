"""Pytest hooks: seed section-registry template cache for script tests."""

from __future__ import annotations

from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
_FIXTURE_REGISTRY = _SCRIPTS_DIR / "test_fixtures" / "section-registry.json"


@pytest.fixture(scope="session", autouse=True)
def _seed_section_registry_cache() -> None:
    workflow_scripts = _SCRIPTS_DIR.parents[1] / "scripts"
    if str(workflow_scripts) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(workflow_scripts))
    from fetch_template import atomic_write, cache_path  # noqa: WPS433
    from subagent_config import detect_platform  # noqa: WPS433

    cache = cache_path(_SCRIPTS_DIR, detect_platform(), "tech-plan", "tpt_section_registry_url")
    if not cache.exists() or not cache.read_text(encoding="utf-8").strip():
        atomic_write(cache, _FIXTURE_REGISTRY.read_text(encoding="utf-8"))
