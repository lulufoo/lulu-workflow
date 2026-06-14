"""Ensure orchestrator scripts/ wins import resolution for hook_guard et al."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
_ORCH_HOOK_GUARD = (_SCRIPTS / "hook_guard.py").as_posix()


def _ensure_orchestrator_scripts() -> None:
    scripts = str(_SCRIPTS)
    while scripts in sys.path:
        sys.path.remove(scripts)
    sys.path.insert(0, scripts)

    mod = sys.modules.get("hook_guard")
    if mod is None:
        return
    mod_file = (getattr(mod, "__file__", None) or "").replace("\\", "/")
    if mod_file != _ORCH_HOOK_GUARD:
        del sys.modules["hook_guard"]


@pytest.fixture(autouse=True)
def _orchestrator_scripts_first():
    _ensure_orchestrator_scripts()
    yield
    _ensure_orchestrator_scripts()
