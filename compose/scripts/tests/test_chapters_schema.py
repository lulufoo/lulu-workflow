#!/usr/bin/env python3
"""Tests for chapters_schema.py (fact-first display layer, M1, structural only)."""

from __future__ import annotations

import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent.parent / "section"
sys.path.insert(0, str(_SECTION))

from chapters_schema import (  # noqa: E402
    covered_lenses,
    fact_ids_by_chapter,
    load_chapters,
    save_chapters,
    validate_chapters,
)


def _valid_chapter(**overrides):
    base = {
        "id": "chap-1",
        "anchor_lenses": ["AR"],
        "derived_from": ["cand-AR"],
        "op": "keep",
        "facts": [{"fid": "F-1", "form_lens": "AR"}],
    }
    base.update(overrides)
    return base


def test_validate_accepts_minimal_chapter():
    assert validate_chapters([_valid_chapter()], allowed_lenses=["AR"]) == []


def test_validate_rejects_bad_op():
    errors = validate_chapters([_valid_chapter(op="reshuffle")])
    assert any("op must be one of" in e for e in errors)


def test_validate_rejects_empty_facts_unless_drop():
    errors = validate_chapters([_valid_chapter(facts=[])])
    assert any("L4 no-empty-rendered-chapter" in e for e in errors)
    # drop is exempt (chapter genealogy record, not rendered)
    assert validate_chapters([_valid_chapter(facts=[], op="drop")]) == []


def test_validate_rejects_drop_chapter_with_facts():
    errors = validate_chapters([_valid_chapter(op="drop")])
    assert any("must be empty when op == 'drop'" in e for e in errors)


def test_validate_rejects_form_lens_outside_anchor_lenses():
    # form_lens SC is a real lens but not an anchor of this AR chapter
    bad = _valid_chapter(facts=[{"fid": "F-1", "form_lens": "SC"}])
    errors = validate_chapters([bad], allowed_lenses=["AR", "SC"])
    assert any("must be one of chapter anchor_lenses" in e for e in errors)


def test_validate_rejects_form_lens_outside_section_order():
    bad = _valid_chapter(facts=[{"fid": "F-1", "form_lens": "ZZ"}])
    errors = validate_chapters([bad], allowed_lenses=["AR"])
    assert any("form_lens 'ZZ' not in section_order" in e for e in errors)


def test_validate_rejects_bad_fid_and_derived_from():
    bad = _valid_chapter(
        derived_from=["", 5],
        facts=[{"fid": "A-1", "form_lens": "AR"}],
    )
    errors = validate_chapters([bad])
    assert any("derived_from must be an array of non-empty strings" in e for e in errors)
    assert any("fid must match F-<n>" in e for e in errors)


def test_save_lenient_to_lowercase_lens_keys(tmp_path: Path):
    # M-1: save normalizes (upper-cases) before validating, matching facts/partition.
    path = tmp_path / "_chapters.json"
    lower = _valid_chapter(
        anchor_lenses=["ar"],
        facts=[{"fid": "F-1", "form_lens": "ar"}],
    )
    save_chapters(path, [lower], allowed_lenses=["AR"])
    loaded = load_chapters(path)
    assert loaded[0]["anchor_lenses"] == ["AR"]
    assert loaded[0]["facts"][0]["form_lens"] == "AR"


def test_validate_rejects_duplicate_chapter_and_fact_ids():
    dup_chapters = [_valid_chapter(), _valid_chapter()]
    errors = validate_chapters(dup_chapters)
    assert any("id duplicate" in e for e in errors)

    dup_fact = _valid_chapter(
        facts=[
            {"fid": "F-1", "form_lens": "AR"},
            {"fid": "F-1", "form_lens": "AR"},
        ],
    )
    errors = validate_chapters([dup_fact])
    assert any("duplicate within chapter" in e for e in errors)


def test_validate_rejects_anchor_lens_outside_section_order():
    errors = validate_chapters([_valid_chapter()], allowed_lenses=["SC"])
    assert any("not in section_order" in e for e in errors)


def test_validate_rejects_unexpected_fields():
    bad = _valid_chapter(display_home="chap-1")
    errors = validate_chapters([bad])
    assert any("unexpected fields" in e for e in errors)


def test_save_and_load_roundtrip(tmp_path: Path):
    path = tmp_path / "_chapters.json"
    chapters = [
        _valid_chapter(),
        _valid_chapter(
            id="chap-2",
            anchor_lenses=["GO"],
            facts=[{"fid": "F-2", "form_lens": "GO"}],
        ),
    ]
    save_chapters(path, chapters, allowed_lenses=["AR", "GO"])
    loaded = load_chapters(path)
    assert [c["id"] for c in loaded] == ["chap-1", "chap-2"]


def test_fact_ids_by_chapter_and_covered_lenses():
    chapters = [
        _valid_chapter(
            facts=[
                {"fid": "F-1", "form_lens": "AR"},
                {"fid": "F-2", "form_lens": "SC"},
            ],
        ),
    ]
    by_chapter = fact_ids_by_chapter(chapters)
    assert by_chapter == {"chap-1": ["F-1", "F-2"]}

    facts_by_id = {"F-1": ["AR"], "F-2": ["AR", "SC"]}
    covered = covered_lenses(chapters[0], facts_by_id)
    assert covered == {"AR", "SC"}
    # covered ⊇ anchor invariant (D5)
    assert set(chapters[0]["anchor_lenses"]) <= covered
