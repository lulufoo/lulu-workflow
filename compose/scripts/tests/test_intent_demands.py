#!/usr/bin/env python3
"""Tests for intent_demands shared predicates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bootstrap  # noqa: F401

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
sys.path.insert(0, str(_INDUCTIVE_DIR))
from intent_demands import (  # noqa: E402
    deferred_intent_refs,
    find_demand_manifest,
    is_generation_guaranteed,
    load_manifest_demands,
)


def _write_manifest(directory: Path, demands: list[dict]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "spec-demands.json"
    path.write_text(
        json.dumps({"version": 1, "id_prefix": "SPEC", "demands": demands}),
        encoding="utf-8",
    )
    return path


def test_find_manifest_beside_ref_doc(tmp_path: Path):
    rev = tmp_path / "revision1"
    _write_manifest(rev, [{"id": "SPEC-1", "section": "ST", "summary": "a"}])
    doc = rev / "product-doc.md"
    doc.write_text("# Product\n", encoding="utf-8")
    assert find_demand_manifest(doc) == rev / "spec-demands.json"


def test_find_manifest_absent(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir(parents=True)
    (rev / "product-doc.md").write_text("# Product\n", encoding="utf-8")
    assert find_demand_manifest(rev / "product-doc.md") is None


def test_load_manifest_demands(tmp_path: Path):
    rev = tmp_path / "revision1"
    _write_manifest(rev, [{"id": "SPEC-1", "section": "ST", "summary": "a"}])
    demands = load_manifest_demands(rev / "product-doc.md")
    assert [d["id"] for d in demands] == ["SPEC-1"]


def test_is_generation_guaranteed_true_when_manifest_nonempty(tmp_path: Path):
    rev = tmp_path / "revision1"
    _write_manifest(rev, [{"id": "SPEC-1", "section": "ST", "summary": "a"}])
    refs = [{"type": "lulu-spec", "path": str(rev / "product-doc.md")}]
    assert is_generation_guaranteed(refs) is True


def test_is_generation_guaranteed_false_when_no_manifest(tmp_path: Path):
    rev = tmp_path / "revision1"
    rev.mkdir(parents=True)
    (rev / "product-doc.md").write_text("# Product\n", encoding="utf-8")
    refs = [{"type": "lulu-spec", "path": str(rev / "product-doc.md")}]
    assert is_generation_guaranteed(refs) is False


def test_is_generation_guaranteed_false_when_empty_manifest(tmp_path: Path):
    rev = tmp_path / "revision1"
    _write_manifest(rev, [])
    refs = [{"type": "lulu-spec", "path": str(rev / "product-doc.md")}]
    assert is_generation_guaranteed(refs) is False


def test_is_generation_guaranteed_false_for_other_source(tmp_path: Path):
    rev = tmp_path / "revision1"
    _write_manifest(rev, [{"id": "SPEC-1", "section": "ST", "summary": "a"}])
    refs = [{"type": "lulu-spec", "path": str(rev / "product-doc.md")}]
    assert is_generation_guaranteed(refs, source="scope") is False
    assert is_generation_guaranteed(refs, source="ai_scan") is False


def test_is_generation_guaranteed_accepts_legacy_and_prefixed_role_a(
    tmp_path: Path,
):
    rev = tmp_path / "revision1"
    _write_manifest(rev, [{"id": "SPEC-1", "section": "ST", "summary": "a"}])
    refs = [{"type": "lulu-spec", "path": str(rev / "product-doc.md")}]
    assert is_generation_guaranteed(refs) is True
    assert is_generation_guaranteed(refs, source="ai_intent_baseline") is True
    assert is_generation_guaranteed(refs, source="intent_baseline") is True


def test_is_generation_guaranteed_empty_refs():
    assert is_generation_guaranteed([]) is False
    assert is_generation_guaranteed(None) is False


def test_deferred_intent_refs_no_ledger(tmp_path: Path):
    assert deferred_intent_refs(tmp_path) == set()
