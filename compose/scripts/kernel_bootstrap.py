"""Insert compose script directories onto sys.path."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_COMPOSE = _SCRIPTS.parent
_SKILL_SCRIPTS = _COMPOSE.parent / "scripts"
_NARRATIVE_ARC = _COMPOSE / "narrative-arc-runner" / "scripts"


def inductive_schema_dirs(scripts: Path | None = None) -> tuple[Path, ...]:
    root = (scripts or _SCRIPTS) / "inductive" / "schema"
    return (root / "gate", root / "g2", root / "g3", root / "g4")


_DOMAIN_DIRS = (
    _SCRIPTS / "_kernel",
    _SCRIPTS / "session",
    _SCRIPTS / "templates",
    _SCRIPTS / "facts",
    _SCRIPTS / "writing",
    _SCRIPTS / "writing" / "schema",
    _SCRIPTS / "eval",
    _SCRIPTS / "inductive",
    _SCRIPTS / "deductive",
    _SCRIPTS / "scope",
    *inductive_schema_dirs(),
)

_SCHEMA_DIRS = (
    _SCRIPTS / "schema" / "section",
    _SCRIPTS / "schema" / "section" / "registry",
    _SCRIPTS / "schema" / "section" / "document",
    _SCRIPTS / "schema" / "section" / "scope",
    _SCRIPTS / "schema" / "session",
)


def ensure_kernel_paths() -> None:
    for p in (
        _SKILL_SCRIPTS,
        _SCRIPTS,
        *_DOMAIN_DIRS,
        *_SCHEMA_DIRS,
        _NARRATIVE_ARC,
    ):
        s = str(p)
        if s not in sys.path:
            sys.path.insert(0, s)
