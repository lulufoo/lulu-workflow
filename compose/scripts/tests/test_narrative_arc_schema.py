#!/usr/bin/env python3
"""Tests for narrative_arc_schema (archive-5.0)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SECTION = Path(__file__).resolve().parents[1] / "writing"
for _p in (_SECTION, _SECTION / "schema"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from narrative_arc_schema import (  # noqa: E402
    is_write_ready,
    normalize_narrative_arc,
    save_narrative_arc,
    validate_narrative_arc,
)


def _mapped() -> dict:
    return {
        "version": "1",
        "kind": "narrative-arc",
        "status": "mapped",
        "leaves": [
            {
                "id": "A01",
                "title": "Leaf one",
                "fact_ids": ["F-1", "F-2"],
            }
        ],
        "excluded": ["F-3"],
    }


def _write_ready() -> dict:
    return {
        "version": "1",
        "kind": "narrative-arc",
        "status": "write_ready",
        "leaves": [
            {
                "id": "A01",
                "title": "Leaf one",
                "fact_ids": ["F-1", "F-2"],
                "chapters": [
                    {"lens": "I", "fact_ids": ["F-1"]},
                    {"lens": "IF", "fact_ids": ["F-2"]},
                ],
            }
        ],
    }


def test_mapped_ok():
    assert validate_narrative_arc(_mapped()) == []


def test_write_ready_ok():
    assert validate_narrative_arc(_write_ready()) == []
    assert is_write_ready(_write_ready())


def test_write_ready_requires_chapters():
    data = _mapped()
    data["status"] = "write_ready"
    errors = validate_narrative_arc(data)
    assert any("chapters" in e for e in errors)


def test_duplicate_leaf_mapping():
    data = _mapped()
    data["leaves"].append(
        {"id": "A02", "title": "Two", "fact_ids": ["F-1"]},
    )
    errors = validate_narrative_arc(data)
    assert any("multiple leaves" in e for e in errors)


def test_chapter_fact_must_be_in_leaf():
    data = _write_ready()
    data["leaves"][0]["chapters"][0]["fact_ids"] = ["F-9"]
    errors = validate_narrative_arc(data)
    assert any("not in leaf fact_ids" in e for e in errors)


def test_unresolved_blocks_write_ready():
    data = _write_ready()
    data["unresolved"] = ["F-9"]
    errors = validate_narrative_arc(data)
    assert any("unresolved" in e for e in errors)


def test_facts_coverage_and_empty_tags():
    data = _write_ready()
    facts = [
        {"id": "F-1", "text": "a", "lens": "I"},
        {"id": "F-2", "text": "b"},
    ]
    errors = validate_narrative_arc(data, facts=facts)
    assert any("empty lens" in e for e in errors)


def test_chapter_lens_must_be_in_fact_tags():
    data = _write_ready()
    facts = [
        {"id": "F-1", "text": "a", "lens": "ST"},
        {"id": "F-2", "text": "b", "lens": "IF"},
    ]
    errors = validate_narrative_arc(data, facts=facts)
    assert any("is not fact F-1 lens" in e for e in errors)


def test_save_roundtrip(tmp_path: Path):
    path = tmp_path / "_narrative-arc.json"
    save_narrative_arc(path, _write_ready())
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded["status"] == "write_ready"
    assert normalize_narrative_arc(loaded)["leaves"][0]["chapters"][0]["lens"] == "I"


def test_allowed_lenses():
    data = _write_ready()
    errors = validate_narrative_arc(data, allowed_lenses={"I"})
    assert any("not in allowed lenses" in e for e in errors)
