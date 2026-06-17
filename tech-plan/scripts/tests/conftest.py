"""Pytest hooks for tech-plan shell script tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS_ROOT.parents[1]
_KERNEL_TESTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts" / "tests"
_EVAL_SCRIPTS = _WORKFLOW_ROOT / "eval" / "scripts"
for p in (
    _KERNEL_TESTS,
    _SCRIPTS_ROOT / "drafting",
    _SCRIPTS_ROOT / "eval",
    _EVAL_SCRIPTS,
):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import bootstrap  # noqa: F401
from compose_profile_context import reset_active_profile  # noqa: WPS433
from test_template_data import seed_tech_plan_test_caches  # noqa: WPS433


@pytest.fixture(autouse=True)
def _reset_compose_profile() -> None:
    """Avoid leaking compose profile between test modules."""
    reset_active_profile()
    yield
    reset_active_profile()


@pytest.fixture(scope="session")
def project_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("project")
    seed_tech_plan_test_caches(root)
    return root


@pytest.fixture(autouse=True)
def _use_project_template_cache(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import section_registry_schema  # noqa: WPS433

    section_registry_schema._registry_for_path.cache_clear()
    monkeypatch.chdir(project_root)
