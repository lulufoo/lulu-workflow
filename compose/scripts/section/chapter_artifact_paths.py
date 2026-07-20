#!/usr/bin/env python3
"""Path helpers for fact-first display-layer chapter artifacts (M4a).

Case-preserving ``cid`` — chapter ids (``_chapter-framework.json`` /
``_chapter-placement.json`` ``chapters[].id``, e.g. ``chap-3``) are free
stable strings, not uppercase lens keys; case-folding would silently mangle
the path into e.g. ``_derive-CHAP-3.json`` (design rationale, source repo,
why-only: docs/domain/ssot/compose/mechanism-ssot/compose-display-architecture.md;
process how archive: docs/domain/archive/compose/archive-2.0/compose-fact-first-display-layer-design.md §11.4 Major#4;
placement SoT: docs/domain/archive/compose/archive-3.0/).
"""

from __future__ import annotations

from pathlib import Path

CHAPTER_DERIVE_PREFIX = "_derive-"
CHAPTER_BODY_PREFIX = "_body-"


def chapter_derive_path(revision_dir: Path, cid: str) -> Path:
    key = str(cid).strip()
    return Path(revision_dir) / f"{CHAPTER_DERIVE_PREFIX}{key}.json"


def chapter_body_path(revision_dir: Path, cid: str) -> Path:
    key = str(cid).strip()
    return Path(revision_dir) / f"{CHAPTER_BODY_PREFIX}{key}.txt"
