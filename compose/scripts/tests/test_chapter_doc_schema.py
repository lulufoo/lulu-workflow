#!/usr/bin/env python3
"""Tests for chapter_doc_schema.py (fact-first display layer, M4a)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "writing"))

from chapter_doc_schema import (  # noqa: E402
    chapter_anchor_present,
    chapter_body_by_id,
    format_chapter_anchor,
    has_any_chapter_anchor,
    parse_chapter_bodies,
)


def test_format_chapter_anchor_strips():
    assert format_chapter_anchor("  chap-1  ") == "<!-- chapter:chap-1 -->"


def test_format_chapter_anchor_preserves_case():
    assert format_chapter_anchor("CHAP-1") == "<!-- chapter:CHAP-1 -->"


def test_has_any_chapter_anchor():
    assert has_any_chapter_anchor("no anchors here") is False
    assert has_any_chapter_anchor("<!-- chapter:chap-1 -->\n## T\n\nBody.") is True


def test_chapter_anchor_present_is_case_sensitive_id():
    text = "<!-- chapter:chap-1 -->\n## T\n\nBody."
    assert chapter_anchor_present(text, "chap-1") is True
    assert chapter_anchor_present(text, "CHAP-1") is False
    assert chapter_anchor_present(text, "chap-2") is False


def test_parse_chapter_bodies_single():
    text = "<!-- chapter:chap-1 -->\n## Title\n\nBody one."
    bodies = parse_chapter_bodies(text)
    assert bodies == {"chap-1": "## Title\n\nBody one."}


def test_parse_chapter_bodies_multiple_ordered_segments():
    text = (
        "<!-- chapter:chap-1 -->\n## A\n\nBody A.\n\n"
        "---\n\n"
        "<!-- chapter:chap-2 -->\n## B\n\nBody B."
    )
    bodies = parse_chapter_bodies(text)
    assert set(bodies) == {"chap-1", "chap-2"}
    assert "Body A." in bodies["chap-1"]
    assert "Body B." in bodies["chap-2"]
    # Segment for chap-1 must not leak into chap-2's content.
    assert "Body B." not in bodies["chap-1"]


def test_chapter_body_by_id_missing_returns_empty():
    text = "<!-- chapter:chap-1 -->\n## A\n\nBody."
    assert chapter_body_by_id(text, "chap-999") == ""


def test_chapter_body_by_id_empty_segment():
    text = "<!-- chapter:chap-1 --><!-- chapter:chap-2 -->\n## B\n\nBody B."
    assert chapter_body_by_id(text, "chap-1") == ""


def test_has_any_chapter_anchor_is_tag_case_insensitive():
    # The anchor *tag* ("chapter:") is matched case-insensitively (re.IGNORECASE
    # on the whole pattern); only the captured cid is compared case-sensitively
    # elsewhere (test_chapter_anchor_present_is_case_sensitive_id).
    assert has_any_chapter_anchor("<!-- CHAPTER:chap-1 -->\n## T\n\nBody.") is True


def test_parse_chapter_bodies_duplicate_cid_last_segment_wins():
    text = (
        "<!-- chapter:chap-1 -->\n## First\n\nFirst body.\n\n"
        "<!-- chapter:chap-1 -->\n## Second\n\nSecond body."
    )
    bodies = parse_chapter_bodies(text)
    assert "Second body." in bodies["chap-1"]
    assert "First body." not in bodies["chap-1"]


def test_chapter_anchor_present_id_with_hyphens_is_matched_literally():
    text = "<!-- chapter:chap-3-alt.v2 -->\n## T\n\nBody."
    assert chapter_anchor_present(text, "chap-3-alt.v2") is True
    assert chapter_anchor_present(text, "chap-3") is False
