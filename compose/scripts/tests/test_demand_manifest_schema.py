#!/usr/bin/env python3
"""Tests for demand_manifest_schema (producer-side demand manifest helpers)."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401
import pytest
from demand_manifest_schema import (  # noqa: E402
    build_manifest,
    load_manifest,
    manifest_filename,
    parse_units,
    validate_manifest,
    write_manifest,
)


def test_manifest_filename_from_prefix():
    assert manifest_filename("SPEC") == "spec-demands.json"
    assert manifest_filename("Feat") == "feat-demands.json"


def test_manifest_filename_rejects_empty():
    with pytest.raises(ValueError):
        manifest_filename("   ")


def test_build_manifest_mints_sequential_ids():
    units = [
        {"section": "ST", "summary": "decision A"},
        {"section": "KD", "summary": "decision B"},
    ]
    manifest = build_manifest(units, "SPEC")
    assert manifest["version"] == 1
    assert manifest["id_prefix"] == "SPEC"
    ids = [d["id"] for d in manifest["demands"]]
    assert ids == ["SPEC-1", "SPEC-2"]


def test_build_manifest_keeps_explicit_ids_and_fills_gaps():
    units = [
        {"id": "SPEC-3", "section": "ST", "summary": "pinned"},
        {"section": "KD", "summary": "auto"},
    ]
    manifest = build_manifest(units, "SPEC")
    ids = [d["id"] for d in manifest["demands"]]
    # Explicit SPEC-3 preserved; minted id must not collide with it.
    assert ids[0] == "SPEC-3"
    assert ids[1] == "SPEC-1"
    assert len(set(ids)) == 2


def test_build_manifest_preserves_extra_keys():
    units = [{"section": "IF", "summary": "x", "kw": 2, "note": "keep"}]
    manifest = build_manifest(units, "SPEC")
    demand = manifest["demands"][0]
    assert demand["kw"] == 2
    assert demand["note"] == "keep"


def test_validate_manifest_flags_missing_fields():
    bad = {
        "id_prefix": "SPEC",
        "demands": [
            {"id": "SPEC-1", "section": "", "summary": "s"},
            {"id": "SPEC-2", "section": "ST", "summary": ""},
        ],
    }
    errors = validate_manifest(bad)
    assert any("section" in e for e in errors)
    assert any("summary" in e for e in errors)


def test_validate_manifest_flags_prefix_and_dupes():
    bad = {
        "id_prefix": "SPEC",
        "demands": [
            {"id": "FOO-1", "section": "ST", "summary": "s"},
            {"id": "SPEC-1", "section": "ST", "summary": "s"},
            {"id": "SPEC-1", "section": "KD", "summary": "s"},
        ],
    }
    errors = validate_manifest(bad)
    assert any("must start with" in e for e in errors)
    assert any("duplicated" in e for e in errors)


def test_validate_manifest_requires_prefix_and_list():
    assert any("id_prefix" in e for e in validate_manifest({"demands": []}))
    assert any("demands" in e for e in validate_manifest({"id_prefix": "SPEC"}))


def test_write_then_load_roundtrip(tmp_path: Path):
    manifest = build_manifest(
        [{"section": "ST", "summary": "a"}, {"section": "KD", "summary": "b"}],
        "SPEC",
    )
    path = tmp_path / manifest_filename("SPEC")
    write_manifest(path, manifest)
    assert path.name == "spec-demands.json"
    loaded = load_manifest(path)
    assert loaded == manifest


def test_write_manifest_rejects_invalid(tmp_path: Path):
    with pytest.raises(ValueError):
        write_manifest(tmp_path / "x.json", {"id_prefix": "", "demands": []})


def test_parse_units_inline_and_file(tmp_path: Path):
    inline = '[{"section": "ST", "summary": "a"}]'
    assert parse_units(inline) == [{"section": "ST", "summary": "a"}]

    f = tmp_path / "units.json"
    f.write_text(inline, encoding="utf-8")
    assert parse_units(f"@{f}") == [{"section": "ST", "summary": "a"}]


def test_parse_units_rejects_non_array():
    with pytest.raises(ValueError):
        parse_units('{"section": "ST"}')
