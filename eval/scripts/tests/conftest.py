"""Ensure eval/scripts wins import resolution for eval tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EVAL_SCRIPTS = Path(__file__).resolve().parents[1]


def _ensure_eval_scripts() -> None:
    scripts = str(_EVAL_SCRIPTS)
    while scripts in sys.path:
        sys.path.remove(scripts)
    sys.path.insert(0, scripts)


@pytest.fixture(autouse=True)
def _eval_scripts_first():
    _ensure_eval_scripts()
    yield
    _ensure_eval_scripts()


_ensure_eval_scripts()
