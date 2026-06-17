"""Pytest path bootstrap for compose-kernel tests."""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_KERNEL_SCRIPTS = _TESTS.parent
CORE = _KERNEL_SCRIPTS / "core"
SECTION = _KERNEL_SCRIPTS / "section"
SCOPE = _KERNEL_SCRIPTS / "scope"
IO = _KERNEL_SCRIPTS / "io"
SCHEMA_SECTION = _KERNEL_SCRIPTS / "schema" / "section"
SCHEMA_SECTION_REGISTRY = SCHEMA_SECTION / "registry"
SCHEMA_SECTION_ROUND = SCHEMA_SECTION / "round"
SCHEMA_SECTION_DOCUMENT = SCHEMA_SECTION / "document"
SCHEMA_SECTION_SCOPE = SCHEMA_SECTION / "scope"
SCHEMA_SESSION = _KERNEL_SCRIPTS / "schema" / "session"

for p in (
    CORE,
    SECTION,
    SCOPE,
    IO,
    SCHEMA_SECTION_REGISTRY,
    SCHEMA_SECTION_ROUND,
    SCHEMA_SECTION_DOCUMENT,
    SCHEMA_SECTION_SCOPE,
    SCHEMA_SESSION,
    _TESTS,
):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
