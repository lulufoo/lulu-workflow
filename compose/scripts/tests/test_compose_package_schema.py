#!/usr/bin/env python3
"""Tests for compose_package_schema."""

from __future__ import annotations

import json
from pathlib import Path

import bootstrap  # noqa: F401
import pytest
from compose_package_schema import (  # noqa: E402
    build_compose_package,
    chain_dependency_tree_from_package,
    is_compose_package_path,
    load_compose_package,
    missing_slice_docs,
    package_filename_from_doc,
    resolve_focus_doc_path,
    save_compose_package,
    stub_slice_rulers_from_package,
    validate_compose_package,
)


def test_package_filename_from_doc() -> None:
    assert package_filename_from_doc("design-doc.md") == "design-package.json"
    assert package_filename_from_doc("tech-doc.md") == "tech-package.json"
    assert package_filename_from_doc("product-doc.md") == "product-package.json"


def test_validate_accepts_single_l() -> None:
    pkg = build_compose_package(
        profile_id="lulu-design",
        order=["L1"],
        slices=[{"id": "L1", "title": "Only", "doc_path": "L1/design-doc.md"}],
    )
    assert validate_compose_package(pkg) == []


def test_validate_rejects_order_slice_mismatch() -> None:
    pkg = build_compose_package(
        profile_id="lulu-design",
        order=["L1", "L2"],
        slices=[{"id": "L1", "title": "Only", "doc_path": "L1/design-doc.md"}],
    )
    errors = validate_compose_package(pkg)
    assert any("order must cover" in e for e in errors)


def test_save_and_resolve_focus_doc(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    (rev / "L1").mkdir(parents=True)
    (rev / "L2").mkdir()
    (rev / "L1" / "design-doc.md").write_text("# L1\n", encoding="utf-8")
    (rev / "L2" / "design-doc.md").write_text("# L2\n", encoding="utf-8")
    pkg = build_compose_package(
        profile_id="lulu-design",
        order=["L1", "L2"],
        slices=[
            {"id": "L1", "title": "A", "doc_path": "L1/design-doc.md"},
            {"id": "L2", "title": "B", "doc_path": "L2/design-doc.md"},
        ],
    )
    path = save_compose_package(rev, "design-doc.md", pkg)
    assert path.name == "design-package.json"
    loaded = load_compose_package(path)
    assert loaded["order"] == ["L1", "L2"]
    assert resolve_focus_doc_path(loaded, "L2", package_path=path) == (
        rev / "L2" / "design-doc.md"
    ).resolve()
    assert is_compose_package_path(path)


def test_missing_slice_docs(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    pkg = build_compose_package(
        profile_id="lulu-design",
        order=["L1"],
        slices=[{"id": "L1", "title": "Only", "doc_path": "L1/design-doc.md"}],
    )
    assert missing_slice_docs(rev, pkg) == ["L1/design-doc.md"]
    with pytest.raises(ValueError, match="missing slice docs"):
        save_compose_package(rev, "design-doc.md", pkg)


def test_chain_tree_and_stub_rulers() -> None:
    pkg = build_compose_package(
        profile_id="lulu-design",
        order=["L1", "L2", "L3"],
        slices=[
            {"id": "L1", "title": "A", "doc_path": "L1/design-doc.md"},
            {"id": "L2", "title": "B", "doc_path": "L2/design-doc.md"},
            {"id": "L3", "title": "C", "doc_path": "L3/design-doc.md"},
        ],
    )
    tree = chain_dependency_tree_from_package(pkg)
    assert tree["order"] == ["L1", "L2", "L3"]
    assert tree["edges"] == [
        {"from": "L2", "to": "L1"},
        {"from": "L3", "to": "L2"},
    ]
    rulers = stub_slice_rulers_from_package(pkg)
    assert rulers is not None
    assert rulers["cut_axis"] == "upstream_order"
    assert rulers["rulers"]["L1"]["job"] == "A"
    assert rulers["rulers"]["L1"]["in"] == ["TBD"]
    assert stub_slice_rulers_from_package(
        build_compose_package(
            profile_id="lulu-design",
            order=["L1"],
            slices=[{"id": "L1", "title": "Only", "doc_path": "L1/design-doc.md"}],
        )
    ) is None
