#!/usr/bin/env python3
"""Tests for per-section JSON schema (section-SoT)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
sys.path.insert(0, str(_INDUCTIVE_DIR))

from inductive_section_schema import (  # noqa: E402
    load_index,
    load_section,
    mint_decision_id,
    mint_open_id,
    next_decision_seq,
    next_open_seq,
    save_index,
    save_section,
    validate_index,
    validate_section,
)


def test_validate_section_rejects_missing_key():
    bad = {
        "status": "active",
        "frontier_kw": 1,
        "decisions": [],
        "open": [],
        "deferred": [],
    }
    errs = validate_section(bad)
    assert any("key" in e for e in errs)


def test_mint_ids_are_stable_and_section_prefixed():
    assert mint_decision_id("ST", 1) == "ST-d1"
    assert mint_open_id("ST", 1) == "ST-o1"


def test_validate_index_requires_version_and_cycle():
    errs = validate_index({"profile": "lulu-design"})
    assert any("version" in e for e in errs)
    assert any("cycle_id" in e for e in errs)


def test_validate_section_rejects_seed_without_scope_means():
    sec = {
        "key": "ST",
        "status": "active",
        "frontier_kw": 1,
        "decisions": [
            {
                "id": "ST-d1",
                "kw": 1,
                "text": "x",
                "trigger": "seed",
                "means": "ai_scan",
                "confidence": "direct",
            }
        ],
        "open": [],
        "deferred": [],
    }
    errs = validate_section(sec)
    assert any("seed" in e and "scope" in e for e in errs)


def test_validate_section_accepts_minimal_valid():
    sec = {
        "key": "ST",
        "status": "untouched",
        "frontier_kw": 0,
        "decisions": [],
        "open": [],
        "deferred": [],
    }
    assert validate_section(sec) == []


def test_load_save_section_roundtrip(tmp_path: Path):
    out_dir = tmp_path
    sec = {
        "key": "ST",
        "status": "active",
        "frontier_kw": 1,
        "decisions": [
            {
                "id": "ST-d1",
                "kw": 1,
                "text": "限流器置于网关",
                "trigger": "seed",
                "means": "scope",
                "confidence": "direct",
                "code_refs": [],
            }
        ],
        "open": [],
        "deferred": [],
    }
    save_section(out_dir, sec)
    loaded = load_section(out_dir, "ST")
    assert loaded["key"] == "ST"
    assert loaded["decisions"][0]["text"] == "限流器置于网关"
    assert next_decision_seq(loaded) == 2
    assert next_open_seq(loaded) == 1


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
