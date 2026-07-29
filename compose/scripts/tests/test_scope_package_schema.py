#!/usr/bin/env python3
"""Tests for scope_package_schema (archive-1.0 P0)."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401
from scope_package_schema import (  # noqa: E402
    build_scope_package,
    chain_ids_from_scope_package,
    is_scope_package_path,
    load_scope_package,
    save_scope_package,
    validate_scope_package,
)


def test_single_l_ok() -> None:
    pkg = build_scope_package(
        slices=[
            {
                "id": "L1",
                "title": "Only",
                "fact_path": "main/decision-fact.json",
                "source_id": "main",
            }
        ]
    )
    assert validate_scope_package(pkg) == []


def test_rejects_order_edges_empty_slices() -> None:
    pkg = build_scope_package(
        slices=[{"id": "L1", "title": "A", "fact_path": "a.json"}]
    )
    pkg["order"] = ["L1"]
    assert any("order must not" in e for e in validate_scope_package(pkg))
    bad = {"version": 1, "slices": []}
    assert any("non-empty" in e for e in validate_scope_package(bad))


def test_roundtrip_preserves_order(tmp_path: Path) -> None:
    pkg = build_scope_package(
        slices=[
            {"id": "L1", "title": "A", "fact_path": "D1/decision-fact.json", "source_id": "D1"},
            {"id": "L2", "title": "B", "fact_path": "D2/decision-fact.json", "source_id": "D2"},
        ]
    )
    path = save_scope_package(tmp_path, pkg)
    loaded = load_scope_package(path)
    assert chain_ids_from_scope_package(loaded) == ["L1", "L2"]
    assert is_scope_package_path(path)
