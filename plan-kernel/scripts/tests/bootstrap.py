"""Pytest path bootstrap for plan-kernel tests."""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS = Path(__file__).resolve().parent
_KERNEL_SCRIPTS = _TESTS.parent
CORE = _KERNEL_SCRIPTS / "core"
SECTION = _KERNEL_SCRIPTS / "section"
SCHEMA = _KERNEL_SCRIPTS / "schema"

for p in (CORE, SECTION, SCHEMA, _TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
