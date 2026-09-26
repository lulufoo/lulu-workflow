#!/usr/bin/env python3
"""Tests for decision_package_schema (archive-1.0 P0)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_SCHEMA = (
    Path(__file__).resolve().parents[1] / "schema" / "decision_package_schema.py"
)
_spec = importlib.util.spec_from_file_location("decision_package_schema", _SCHEMA)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

build_decision_package = _mod.build_decision_package
validate_decision_package = _mod.validate_decision_package
save_decision_package = _mod.save_decision_package
load_decision_package = _mod.load_decision_package
is_decision_package_path = _mod.is_decision_package_path


def _main() -> dict[str, str]:
    return {

        "decision_doc_path": "decision-doc.md",
    }


def test_empty_slices_ok() -> None:
    pkg = build_decision_package(main=_main(), slices=[])
    assert validate_decision_package(pkg) == []


def test_rejects_order_and_edges() -> None:
    pkg = build_decision_package(main=_main(), slices=[])
    pkg["order"] = ["D1"]
    pkg["edges"] = []
    errors = validate_decision_package(pkg)
    assert any("order must not" in e for e in errors)
    assert any("edges must not" in e for e in errors)


def test_preserves_slice_order_roundtrip(tmp_path: Path) -> None:
    slices = [
        {
            "id": "D1",
            "title": "A",

            "decision_doc_path": "D1/decision-doc.md",
        },
        {
            "id": "D2",
            "title": "B",

            "decision_doc_path": "D2/decision-doc.md",
        },
    ]
    pkg = build_decision_package(main=_main(), slices=slices)
    path = save_decision_package(tmp_path, pkg)
    loaded = load_decision_package(path)
    assert [s["id"] for s in loaded["slices"]] == ["D1", "D2"]
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert [s["id"] for s in raw["slices"]] == ["D1", "D2"]
    assert is_decision_package_path(path)
