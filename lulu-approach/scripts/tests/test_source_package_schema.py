#!/usr/bin/env python3
"""Tests for format-neutral approach source-package delivery."""

from __future__ import annotations

import importlib.util
from pathlib import Path


_SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "source_package_schema.py"
_spec = importlib.util.spec_from_file_location("source_package_schema", _SCHEMA)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

build_source_package = _mod.build_source_package
load_source_package = _mod.load_source_package
save_source_package = _mod.save_source_package
validate_source_package = _mod.validate_source_package


def _slice() -> dict[str, str]:
    return {
        "id": "L1",
        "title": "main",
        "source_path": "main/decision-fact.json",
        "source_id": "main",
    }


def test_roundtrip_requires_committed_delivery_shape(tmp_path: Path) -> None:
    package = build_source_package(
        holder_stage="lulu-approach",
        slices=[_slice()],
        commit_status="committed",
    )
    path = save_source_package(tmp_path, package)
    assert load_source_package(path) == package


def test_rejects_decision_internal_paths_and_uncommitted_status() -> None:
    package = build_source_package(
        holder_stage="lulu-approach",
        slices=[{**_slice(), "decision_doc_path": "main/decision-doc.md"}],
        commit_status="draft",
    )
    errors = validate_source_package(package)
    assert any("unexpected keys" in error for error in errors)
    assert any("commit_status" in error for error in errors)
