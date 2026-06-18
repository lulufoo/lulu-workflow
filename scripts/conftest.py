"""Ensure orchestrator scripts/ wins import resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent


def _ensure_orchestrator_scripts() -> None:
    scripts = str(_SCRIPTS)
    while scripts in sys.path:
        sys.path.remove(scripts)
    sys.path.insert(0, scripts)


@pytest.fixture(autouse=True)
def _orchestrator_scripts_first():
    _ensure_orchestrator_scripts()
    yield
    _ensure_orchestrator_scripts()
