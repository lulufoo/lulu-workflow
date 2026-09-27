#!/usr/bin/env python3
"""Path helpers for fact-first display-layer chapter artifacts (M4a).

Case-preserving ``cid`` — narrative-arc chapter ids are ``{leaf.id}-{lens}``
(e.g. ``A01-AR``); case-folding would silently mangle paths into e.g.
``_derive-A01-ar.json``. Design rationale (lulu-skills-workspace, why-only):
docs/ssot/compose/mechanism-ssot/compose-display-architecture.md;
process how: docs/archive/lulu-workflow/compose/archive-5.0/.
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
