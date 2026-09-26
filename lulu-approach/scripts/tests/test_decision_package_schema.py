#!/usr/bin/env python3
"""Tests for decision_package_schema (v2: one decision doc per package)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

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
    return {"decision_doc_path": "decision-doc.md"}


def test_main_only_package_ok() -> None:
    pkg = build_decision_package(main=_main())
    assert validate_decision_package(pkg) == []
    assert set(pkg) == {"version", "status", "main"}
    assert pkg["version"] == 2


def test_rejects_extra_top_level_keys() -> None:
    pkg = build_decision_package(main=_main())
    pkg["slices"] = []
    pkg["order"] = ["D1"]
    errors = validate_decision_package(pkg)
    assert any("unexpected keys" in e for e in errors)


def test_rejects_absolute_or_escaping_doc_path() -> None:
    assert validate_decision_package(
        build_decision_package(main={"decision_doc_path": "/abs/decision-doc.md"})
    )
    assert validate_decision_package(
        build_decision_package(main={"decision_doc_path": "../decision-doc.md"})
    )


def test_roundtrip(tmp_path: Path) -> None:
    pkg = build_decision_package(main=_main(), status="draft")
    path = save_decision_package(tmp_path, pkg)
    loaded = load_decision_package(path)
    assert loaded == pkg
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["main"]["decision_doc_path"] == "decision-doc.md"
    assert "slices" not in raw
    assert is_decision_package_path(path)
