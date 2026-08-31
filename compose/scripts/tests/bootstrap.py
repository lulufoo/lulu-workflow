"""Pytest path bootstrap for compose tests."""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_KERNEL_SCRIPTS = _TESTS.parent
KERNEL = _KERNEL_SCRIPTS / "_kernel"
SESSION = _KERNEL_SCRIPTS / "session"
TEMPLATES = _KERNEL_SCRIPTS / "templates"
FACTS = _KERNEL_SCRIPTS / "facts"
WRITING = _KERNEL_SCRIPTS / "writing"
EVAL = _KERNEL_SCRIPTS / "eval"
INDUCTIVE = _KERNEL_SCRIPTS / "inductive"
DEDUCTIVE = _KERNEL_SCRIPTS / "deductive"
SCOPE = _KERNEL_SCRIPTS / "scope"
SCHEMA_SECTION = _KERNEL_SCRIPTS / "schema" / "section"
SCHEMA_SECTION_REGISTRY = SCHEMA_SECTION / "registry"
SCHEMA_SECTION_DOCUMENT = SCHEMA_SECTION / "document"
SCHEMA_SECTION_SCOPE = SCHEMA_SECTION / "scope"
SCHEMA_SESSION = _KERNEL_SCRIPTS / "schema" / "session"

# Bare module names owned exclusively by compose (stage trees use prefixed names).
_MODULE_OWNERS = {
    "workflow_common": KERNEL,
    "workflow_state_schema": SCHEMA_SESSION,
    "session_state_schema": SCHEMA_SESSION,
    "session_control": SESSION,
}


def _purge_stale_modules() -> None:
    """Drop cached modules that were imported from outside compose."""
    for name, expected_dir in _MODULE_OWNERS.items():
        mod = sys.modules.get(name)
        if mod is None:
            continue
        mod_file = getattr(mod, "__file__", None)
        if not mod_file:
            del sys.modules[name]
            continue
        try:
            Path(mod_file).resolve().relative_to(Path(expected_dir).resolve())
        except ValueError:
            del sys.modules[name]


_purge_stale_modules()

_COMPOSE_PATHS = (
    KERNEL,
    SESSION,
    TEMPLATES,
    FACTS,
    WRITING,
    EVAL,
    INDUCTIVE,
    DEDUCTIVE,
    SCOPE,
    INDUCTIVE / "schema",
    SCHEMA_SECTION,
    SCHEMA_SECTION_REGISTRY,
    SCHEMA_SECTION_DOCUMENT,
    SCHEMA_SECTION_SCOPE,
    SCHEMA_SESSION,
    _KERNEL_SCRIPTS,
    _TESTS,
)

_WORKFLOW_ROOT = _TESTS.parent.parent.parent
_OTHER_STAGE_SCRIPT_DIRS = (
    _WORKFLOW_ROOT / "lulu-code" / "scripts",
    _WORKFLOW_ROOT / "eval" / "scripts",
)


def _deprioritize_other_stage_paths() -> None:
    for path in _OTHER_STAGE_SCRIPT_DIRS:
        entry = str(path)
        while entry in sys.path:
            sys.path.remove(entry)


def _prioritize_compose_paths() -> None:
    _deprioritize_other_stage_paths()
    for path in reversed(_COMPOSE_PATHS):
        entry = str(path)
        while entry in sys.path:
            sys.path.remove(entry)
        sys.path.insert(0, entry)


for p in _COMPOSE_PATHS:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

_prioritize_compose_paths()


def refresh_compose_import_paths() -> None:
    """Re-run purge + path priority after another tree imported compose-owned module names."""
    _deprioritize_other_stage_paths()
    _purge_stale_modules()
    _prioritize_compose_paths()
