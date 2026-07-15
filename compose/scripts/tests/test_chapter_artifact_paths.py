#!/usr/bin/env python3
"""Tests for chapter_artifact_paths.py (fact-first display layer, M4a)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "section"))

from chapter_artifact_paths import chapter_body_path, chapter_derive_path  # noqa: E402


def test_chapter_derive_path_preserves_case(tmp_path: Path):
    path = chapter_derive_path(tmp_path, "chap-3")
    assert path.name == "_derive-chap-3.json"


def test_chapter_body_path_preserves_case(tmp_path: Path):
    path = chapter_body_path(tmp_path, "chap-3")
    assert path.name == "_body-chap-3.txt"


def test_chapter_paths_do_not_uppercase_mixed_case_id(tmp_path: Path):
    # Regression guard for Grok M4 review Major#4: reusing the section
    # helper's .upper() would silently mangle chap-3 -> CHAP-3.
    assert chapter_derive_path(tmp_path, "Chap-3").name == "_derive-Chap-3.json"
    assert chapter_body_path(tmp_path, "Chap-3").name == "_body-Chap-3.txt"


def test_chapter_paths_strip_whitespace(tmp_path: Path):
    assert chapter_derive_path(tmp_path, "  chap-1  ").name == "_derive-chap-1.json"
