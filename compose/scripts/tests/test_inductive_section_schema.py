#!/usr/bin/env python3
"""Tests for per-section maturity schema (K4 slim — key/status/frontier_kw only)."""

from __future__ import annotations

import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
sys.path.insert(0, str(_INDUCTIVE_DIR))

from inductive_section_schema import (  # noqa: E402
    empty_section,
    load_index,
    load_section,
    save_index,
    save_section,
    validate_index,
    validate_section,
)


def test_validate_section_rejects_missing_key():
    bad = {
        "status": "active",
        "frontier_kw": 1,
    }
    errs = validate_section(bad)
    assert any("key" in e for e in errs)


def test_validate_section_rejects_legacy_body_fields():
    sec = {
        "key": "ST",
        "status": "active",
        "frontier_kw": 1,
        "decisions": [],
        "open": [],
        "deferred": [],
    }
    errs = validate_section(sec)
    assert any("unexpected" in e for e in errs)


def test_validate_index_requires_version_and_cycle():
    errs = validate_index({"profile": "lulu-design"})
    assert any("version" in e for e in errs)
    assert any("cycle_id" in e for e in errs)


def test_validate_section_accepts_minimal_valid():
    sec = {
        "key": "ST",
        "status": "untouched",
        "frontier_kw": 0,
    }
    assert validate_section(sec) == []


def test_empty_section_has_no_body_arrays():
    doc = empty_section("RN")
    assert doc == {"key": "RN", "status": "untouched", "frontier_kw": 0}
    assert "decisions" not in doc
    assert "open" not in doc
    assert "deferred" not in doc


def test_load_save_section_roundtrip(tmp_path: Path):
    out_dir = tmp_path
    sec = {
        "key": "ST",
        "status": "active",
        "frontier_kw": 1,
    }
    save_section(out_dir, sec)
    loaded = load_section(out_dir, "ST")
    assert loaded["key"] == "ST"
    assert loaded["status"] == "active"
    assert loaded["frontier_kw"] == 1


def test_load_save_index_roundtrip(tmp_path: Path):
    idx = {
        "version": "1",
        "cycle_id": "c1",
        "profile": "lulu-design",
        "scope_ref": "approach-doc.md",
        "section_order_ref": "section-registry",
        "last_checkpoint": None,
    }
    assert validate_index(idx) == []
    save_index(tmp_path, idx)
    loaded = load_index(tmp_path)
    assert loaded["cycle_id"] == "c1"
    assert (tmp_path / "inductive-scope" / "_index.json").exists()
