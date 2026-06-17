"""Pytest hooks for tech-design script tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_KERNEL_CORE = (
    Path(__file__).resolve().parents[3]
    / "compose-kernel"
    / "scripts"
    / "core"
)
if str(_KERNEL_CORE) not in sys.path:
    sys.path.insert(0, str(_KERNEL_CORE))

from compose_profile_context import reset_active_profile  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_compose_profile() -> None:
    """Avoid leaking tech-design profile into other test modules."""
    reset_active_profile()
    yield
    reset_active_profile()


@pytest.fixture(autouse=True)
def _use_tmp_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Match production: template cache resolves under project root (tmp_path)."""
    monkeypatch.chdir(tmp_path)
