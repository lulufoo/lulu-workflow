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
from opens_schema import save_opens, opens_path  # noqa: E402


def _write_manifest(directory: Path, demands: list[dict]) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "spec-demands.json"
    path.write_text(
        json.dumps({"version": 1, "id_prefix": "SPEC", "demands": demands}),
        encoding="utf-8",
    )
    return path


def _minimal_open(
    oid: str,
    *,
    status: str = "open",
    intent_ref: str | None = None,
    blocking: bool = False,
    note: str | None = None,
) -> dict:
    item: dict = {
        "id": oid,
        "status": status,
        "source": {"trigger": "ai", "means": "ai_probe"},
        "kw": 1,
        "blocking": blocking,
        "problem": "gap",
        "resolved_by": [],
    }
    if intent_ref is not None:
        item["intent_ref"] = intent_ref
    if note is not None:
        item["note"] = note
    if status == "deferred" and note is None:
        item["note"] = "skip"
    return item


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


def test_deferred_intent_refs(tmp_path: Path):
    """K4: deferred intent_refs come from inductive-opens.json, not section JSON."""
    save_opens(
        opens_path(tmp_path),
        [
            _minimal_open("O-1", status="deferred", intent_ref="SPEC-1", note="skip"),
            _minimal_open("O-2", status="deferred", intent_ref="SPEC-3", note="skip"),
            _minimal_open("O-3", status="deferred", note="no ref"),
            _minimal_open("O-4", status="open", intent_ref="SPEC-2", blocking=True),
        ],
    )
    assert deferred_intent_refs(tmp_path) == {"SPEC-1", "SPEC-3"}


def test_deferred_intent_refs_no_ledger(tmp_path: Path):
    assert deferred_intent_refs(tmp_path) == set()


def test_check_coverage_blocks_on_doc_open(tmp_path: Path):
    """Exit predicate reads inductive-opens.json blocking opens (K4)."""
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
    code, add_payload = run(
        "add-open",
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
        "--detected-under",
        "ST",
    )
    assert code == 0, add_payload
    code, cov = run("check-coverage")
    assert code == 1
    assert cov.get("ok") is False
    assert any("blocking open" in e for e in cov.get("errors", []))
