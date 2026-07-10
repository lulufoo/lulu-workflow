#!/usr/bin/env python3
"""Tests for intent_demands shared predicates (design §5.5)."""

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


def test_is_generation_guaranteed_empty_refs():
    assert is_generation_guaranteed([]) is False
    assert is_generation_guaranteed(None) is False


def test_deferred_intent_refs(tmp_path: Path):
    scope = tmp_path / "inductive-scope"
    scope.mkdir(parents=True)
    (scope / "ST.json").write_text(
        json.dumps(
            {
                "key": "ST",
                "status": "active",
                "frontier_kw": 1,
                "decisions": [],
                "open": [],
                "deferred": [
                    {"id": "ST-o1", "kw": 2, "note": "skip", "intent_ref": "SPEC-1"},
                    {"id": "ST-o2", "kw": 2, "note": "skip", "intent_ref": "SPEC-3"},
                    {"id": "ST-o3", "kw": 2, "note": "no ref"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (scope / "IF.json").write_text(
        json.dumps(
            {
                "key": "IF",
                "status": "active",
                "frontier_kw": 1,
                "decisions": [
                    {
                        "id": "IF-d1",
                        "kw": 1,
                        "text": "done",
                        "trigger": "ai",
                        "means": "intent_baseline",
                        "confidence": "direct",
                        "intent_ref": "SPEC-2",
                    }
                ],
                "open": [],
                "deferred": [],
            }
        ),
        encoding="utf-8",
    )
    assert deferred_intent_refs(tmp_path) == {"SPEC-1", "SPEC-3"}


def test_deferred_intent_refs_no_ledger(tmp_path: Path):
    assert deferred_intent_refs(tmp_path) == set()


def test_check_coverage_blocks_on_section_open(tmp_path: Path):
    """Exit predicate reads section JSON open[], not exposed-points ledger."""
    import subprocess
    import sys

    ctl = Path(__file__).resolve().parent.parent / "inductive" / "inductive_g3_section_control.py"

    def run(*args: str) -> tuple[int, dict]:
        res = subprocess.run(
            [sys.executable, str(ctl), "--out-dir", str(tmp_path), *args],
            capture_output=True,
            text=True,
        )
        try:
            payload = json.loads(res.stdout)
        except json.JSONDecodeError:
            payload = {"ok": False, "raw": res.stdout, "stderr": res.stderr}
        return res.returncode, payload

    code, payload = run("init-pointer", "--sections", "I,ST", "--mandatory", "")
    assert code == 0, payload
    run("activate-section", "--section", "ST")
    run(
        "add-open",
        "--section",
        "ST",
        "--kw",
        "1",
        "--trigger",
        "ai",
        "--means",
        "probe",
        "--problem",
        "gap",
        "--blocking",
        "true",
    )
    code, cov = run("check-coverage")
    assert code == 1
    assert cov.get("ok") is False
    assert any("blocking open" in e for e in cov.get("errors", []))
