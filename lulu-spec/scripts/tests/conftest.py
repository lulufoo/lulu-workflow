"""Pytest hooks for lulu-spec script tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_TESTS = _ROOT / "compose" / "scripts" / "tests"
_KERNEL_CORE = _ROOT / "compose" / "scripts" / "core"
_START = _ROOT / "lulu-spec" / "scripts" / "start"
_EVAL_DIR = _ROOT / "lulu-spec" / "scripts" / "eval"
_EVAL = _ROOT / "lulu-spec" / "scripts" / "eval"

for entry in (_KERNEL_TESTS, _KERNEL_CORE, _START, _EVAL_DIR, _EVAL, _ROOT / "compose" / "scripts"):
    path = str(entry)
    if path not in sys.path:
        sys.path.insert(0, path)

import bootstrap  # noqa: F401,E402
from compose_profile_context import reset_active_profile  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_compose_profile() -> None:
    """Avoid leaking lulu-spec profile into other test modules."""
    reset_active_profile()
    yield
    reset_active_profile()


@pytest.fixture(autouse=True)
def _use_tmp_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Match production: template cache resolves under project root (tmp_path)."""
    monkeypatch.chdir(tmp_path)
