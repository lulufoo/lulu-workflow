#!/usr/bin/env python3
"""Chapter-level document anchor grammar (fact-first display layer, M4a).

Dual to ``compose_doc_schema.py``'s ``<!-- section-key:KEY -->`` grammar, but
chapter-scoped: ``<!-- chapter:{cid} -->``. The two grammars are flag-branch
alternatives, never mixed in one document — ``display_layer=true`` writes
only chapter anchors, ``display_layer=false``(/absent) writes only
section-key anchors (design SSOT
docs/biz/compose-fact-first-display-layer-design.md §10#7, §11.4).

``cid`` is deliberately **not** case-folded: it is a free stable id from
``_chapters.json[].id`` (e.g. ``chap-3``), not an uppercase lens key (design
SSOT §11.4 Major#4).

Write-side + Init-internal-read (``compose_doc_control append-chapter``,
``init_compose_validation`` display_layer assembly gate). Downstream Eval
reads chapter anchors **from EvalTarget B only** via
``eval/scripts/eval_target_units.py`` (K3-c option 1) — this module stays
compose-side and is **not** imported by eval.
"""

from __future__ import annotations

import re

_CHAPTER_ANCHOR_RE = re.compile(r"<!--\s*chapter:\s*(\S+?)\s*-->", re.IGNORECASE)


def format_chapter_anchor(cid: str) -> str:
    """Return the chapter anchor comment line for one chapter id."""
    return f"<!-- chapter:{str(cid).strip()} -->"


def has_any_chapter_anchor(text: str) -> bool:
    """True if ``text`` already contains at least one chapter anchor."""
    return _CHAPTER_ANCHOR_RE.search(text) is not None


def chapter_anchor_present(text: str, cid: str) -> bool:
    """True if a chapter anchor for ``cid`` already exists in ``text``."""
    key = str(cid).strip()
    return any(match.group(1) == key for match in _CHAPTER_ANCHOR_RE.finditer(text))


def parse_chapter_bodies(text: str) -> dict[str, str]:
    """Return cid -> body segment (between this chapter's anchor and the next).

    Duplicate ``cid`` anchors are not expected in a well-formed document
    (``append_chapter`` rejects them), but if present anyway, the **last**
    matching segment wins — earlier segments for the same ``cid`` are
    silently overwritten (N4, round-1 Grok review of M4a)."""
    matches = list(_CHAPTER_ANCHOR_RE.finditer(text))
    bodies: dict[str, str] = {}
    for index, match in enumerate(matches):
        cid = match.group(1)
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        bodies[cid] = text[start:end].strip()
    return bodies


def chapter_body_by_id(text: str, cid: str) -> str:
    """Return the body segment for one chapter id, or ``''`` when absent."""
    return parse_chapter_bodies(text).get(str(cid).strip(), "")
