#!/usr/bin/env python3
"""Path helpers for fact-first display-layer chapter artifacts (M4a).

Case-preserving ``cid`` — deliberately **not** the section-path convention in
``init_artifact_paths.py`` (which forces ``.upper()`` for section keys).
Chapter ids (``_chapters.json[].id``, e.g. ``chap-3``) are free stable
strings, not uppercase lens keys; reusing the section helpers would silently
mangle the path into e.g. ``_derive-CHAP-3.json`` (design SSOT
docs/biz/compose-fact-first-display-layer-design.md §11.4 Major#4).
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
