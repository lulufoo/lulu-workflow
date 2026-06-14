"""Pytest hooks: seed section-registry template cache for script tests."""

from __future__ import annotations

from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
_FIXTURE_REGISTRY = _SCRIPTS_DIR / "test_fixtures" / "section-registry.json"
_WORKFLOW_SCRIPTS = _SCRIPTS_DIR.parents[2] / "scripts"


@pytest.fixture(scope="session")
def project_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Session project root with section-registry template cache (pytest temp dir)."""
    root = tmp_path_factory.mktemp("project")
    if str(_WORKFLOW_SCRIPTS) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_WORKFLOW_SCRIPTS))
    from fetch_template import atomic_write, cache_path  # noqa: WPS433
    from subagent_config import detect_platform  # noqa: WPS433

    cache = cache_path(root, detect_platform(), "tech-plan", "tpt_section_registry_url")
    atomic_write(cache, _FIXTURE_REGISTRY.read_text(encoding="utf-8"))
    return root


@pytest.fixture(autouse=True)
def _use_project_registry_cache(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve default registry via project_root (matches production cache layout)."""
    import section_registry_schema  # noqa: WPS433

    section_registry_schema._registry_for_path.cache_clear()
    monkeypatch.chdir(project_root)
