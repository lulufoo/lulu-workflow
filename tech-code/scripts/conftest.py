"""Ensure tech-code/scripts wins import resolution over compose-kernel schema paths."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TECH_CODE_SCRIPTS = Path(__file__).resolve().parent
_COMPOSE_SESSION_STATE = (
    _TECH_CODE_SCRIPTS.parents[1]
    / "compose-kernel"
    / "scripts"
    / "schema"
    / "session"
    / "session_state_schema.py"
)

_CONFLICTING_MODULE_NAMES = (
    "workflow_common",
    "workflow_state_schema",
    "session_state_schema",
    "session_control",
)


def _ensure_tech_code_scripts() -> None:
    scripts = str(_TECH_CODE_SCRIPTS)
    while scripts in sys.path:
        sys.path.remove(scripts)
    sys.path.insert(0, scripts)

    mod = sys.modules.get("session_state_schema")
    if mod is None:
        return
    mod_file = (getattr(mod, "__file__", None) or "").replace("\\", "/")
    expected = (_TECH_CODE_SCRIPTS / "session_state_schema.py").as_posix()
    if mod_file != expected:
        del sys.modules["session_state_schema"]


def _purge_non_tech_code_modules() -> None:
    for name in _CONFLICTING_MODULE_NAMES:
        mod = sys.modules.get(name)
        if mod is None:
            continue
        mod_file = getattr(mod, "__file__", None)
        if not mod_file:
            del sys.modules[name]
            continue
        try:
            Path(mod_file).resolve().relative_to(_TECH_CODE_SCRIPTS.resolve())
        except ValueError:
            del sys.modules[name]


def pytest_collect_directory(path, parent):
    if "tech-code/scripts" in str(path):
        _ensure_tech_code_scripts()
        _purge_non_tech_code_modules()
    return None


@pytest.fixture(autouse=True)
def _tech_code_scripts_first(request):
    if "tech-code/scripts" not in str(request.fspath):
        yield
        return
    _ensure_tech_code_scripts()
    _purge_non_tech_code_modules()
    yield
    _ensure_tech_code_scripts()
    _purge_non_tech_code_modules()
