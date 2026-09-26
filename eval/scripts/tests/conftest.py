"""Ensure eval/scripts and capability folders win import resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EVAL_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_EVAL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_EVAL_SCRIPTS))
from eval_path import ensure_eval_script_layers  # noqa: E402


def _ensure_eval_scripts() -> None:
    ensure_eval_script_layers()


@pytest.fixture(autouse=True)
def _eval_scripts_first():
    _ensure_eval_scripts()
    yield
    _ensure_eval_scripts()


_ensure_eval_scripts()
