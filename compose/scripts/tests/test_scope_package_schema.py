#!/usr/bin/env python3
"""Tests for scope_package_schema v2 (single source document)."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401
from scope_package_schema import (  # noqa: E402
    build_scope_package,
    is_scope_package_path,
    load_scope_package,
    save_scope_package,
    validate_scope_package,
)


def test_single_source_ok() -> None:
    pkg = build_scope_package(
        source_path="/abs/decision-doc.md",
        source_id="main",
        title="Only",
    )
    assert validate_scope_package(pkg) == []
    assert pkg["version"] == 2
    assert "slices" not in pkg


def test_rejects_slices_and_empty_path() -> None:
    pkg = build_scope_package(source_path="/abs/decision-doc.md")
    pkg["slices"] = []
    assert any("unknown keys" in e for e in validate_scope_package(pkg))
    assert any("source_path" in e for e in validate_scope_package({"version": 2}))


def test_roundtrip(tmp_path: Path) -> None:
    pkg = build_scope_package(source_path="/abs/decision-doc.md", title="A")
    path = save_scope_package(tmp_path, pkg)
    loaded = load_scope_package(path)
    assert loaded["source_path"] == "/abs/decision-doc.md"
    assert is_scope_package_path(path)
