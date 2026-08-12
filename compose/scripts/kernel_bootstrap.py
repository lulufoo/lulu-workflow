"""Insert compose script directories onto sys.path."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_COMPOSE = _SCRIPTS.parent
_SKILL_SCRIPTS = _COMPOSE.parent / "scripts"
_CORE = _SCRIPTS / "core"
_SECTION = _SCRIPTS / "section"
_DEDUCTIVE = _SCRIPTS / "deductive"
_SCOPE = _SCRIPTS / "scope"
_IO = _SCRIPTS / "io"
_SCHEMA_SECTION = _SCRIPTS / "schema" / "section"
_SCHEMA_SECTION_REGISTRY = _SCHEMA_SECTION / "registry"
_SCHEMA_SECTION_DOCUMENT = _SCHEMA_SECTION / "document"
_SCHEMA_SECTION_SCOPE = _SCHEMA_SECTION / "scope"
_SCHEMA_SESSION = _SCRIPTS / "schema" / "session"
_START = _SCRIPTS / "start"
# Collab schema lives under narrative-arc-runner; Formal schema stays in section/.
_NARRATIVE_ARC = _COMPOSE / "narrative-arc-runner" / "scripts"


def ensure_kernel_paths() -> None:
    for p in (
        _SKILL_SCRIPTS,
        _SCRIPTS,
        _CORE,
        _SECTION,
        _DEDUCTIVE,
        _SCOPE,
        _IO,
        _START,
        _SCHEMA_SECTION,
        _SCHEMA_SECTION_REGISTRY,
        _SCHEMA_SECTION_DOCUMENT,
        _SCHEMA_SECTION_SCOPE,
        _SCHEMA_SESSION,
        _NARRATIVE_ARC,
    ):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
