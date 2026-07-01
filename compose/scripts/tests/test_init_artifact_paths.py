#!/usr/bin/env python3
"""Tests for init artifact paths and title map schemas."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "section"))

from init_artifact_paths import (  # noqa: E402
    BLOCK_TITLES_BASENAME,
    DISPLAY_TITLES_BASENAME,
    block_titles_path,
    body_path,
    derive_path,
    display_titles_path,
)
from init_block_titles_schema import load_block_titles, set_block_title  # noqa: E402
from init_display_titles_schema import (  # noqa: E402
    load_display_titles,
    set_display_title,
    validate_display_titles,
)
from _title_map_io import load_map, validate_flat_string_map  # noqa: E402


def test_derive_and_body_paths(tmp_path: Path):
    revision = tmp_path / "revision1"
    assert derive_path(revision, "ctx").name == "_derive-CTX.json"
    assert body_path(revision, "go").name == "_body-GO.txt"
    assert display_titles_path(revision).name == DISPLAY_TITLES_BASENAME
    assert block_titles_path(revision).name == BLOCK_TITLES_BASENAME


def test_validate_display_titles_rejects_empty_values():
    errors = validate_display_titles({"CTX": ""})
    assert errors


def test_set_display_title_merges(tmp_path: Path):
    revision = tmp_path / "revision1"
    revision.mkdir()
    set_display_title(revision, "CTX", "现状")
    set_display_title(revision, "GO", "目标")
    data = load_display_titles(display_titles_path(revision))
    assert data == {"CTX": "现状", "GO": "目标"}


def test_set_block_title_persists(tmp_path: Path):
    revision = tmp_path / "revision1"
    revision.mkdir()
    path = set_block_title(revision, "OV", "1. 问题与目标")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["OV"] == "1. 问题与目标"


def test_validate_flat_string_map_requires_object():
    assert validate_flat_string_map([], label="x")

def test_load_map_rejects_empty_key(tmp_path: Path):
    path = tmp_path / "_title-display.json"
    path.write_text(json.dumps({"": "x"}, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty map key"):
        load_map(path)


def test_display_and_block_maps_same_abbrev(tmp_path: Path):
    """VF can mean a section display title and a block reader title independently."""
    revision = tmp_path / "revision1"
    revision.mkdir()
    set_display_title(revision, "VF", "验证与收尾")
    set_block_title(revision, "VF", "4. 验证")
    display = load_display_titles(display_titles_path(revision))
    block = load_block_titles(block_titles_path(revision))
    assert display["VF"] == "验证与收尾"
    assert block["VF"] == "4. 验证"

