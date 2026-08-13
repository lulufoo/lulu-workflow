#!/usr/bin/env python3
"""Tests for compose_package_schema."""

from __future__ import annotations

import json
from pathlib import Path

import bootstrap  # noqa: F401
import pytest
from compose_package_schema import (  # noqa: E402
    build_compose_package,
    is_compose_package_path,
    load_compose_package,
    missing_slice_docs,
    package_filename_from_doc,
    resolve_focus_doc_path,
    save_compose_package,
    validate_compose_package,
)


def test_package_filename_from_doc() -> None:
    assert package_filename_from_doc("design-doc.md") == "design-package.json"
    assert package_filename_from_doc("tech-doc.md") == "tech-package.json"
    assert package_filename_from_doc("product-doc.md") == "product-package.json"


def test_build_omits_order() -> None:
    pkg = build_compose_package(
        profile_id="lulu-design",
        slices=[{"id": "L1", "title": "Only", "doc_path": "L1/design-doc.md"}],
    )
    assert "order" not in pkg
    assert validate_compose_package(pkg) == []


def test_validate_accepts_single_l() -> None:
    pkg = build_compose_package(
        profile_id="lulu-design",
        slices=[{"id": "L1", "title": "Only", "doc_path": "L1/design-doc.md"}],
    )
    assert validate_compose_package(pkg) == []


def test_validate_rejects_legacy_order() -> None:
    pkg = {
        "version": 1,
        "profile_id": "lulu-design",
        "order": ["L2", "L1"],
        "slices": [
            {"id": "L1", "title": "A", "doc_path": "L1/design-doc.md"},
            {"id": "L2", "title": "B", "doc_path": "L2/design-doc.md"},
        ],
    }
    errors = validate_compose_package(pkg)
    assert any("order must not" in e for e in errors)


def test_validate_rejects_duplicate_slice_ids() -> None:
    pkg = {
        "version": 1,
        "profile_id": "lulu-design",
        "slices": [
            {"id": "L1", "title": "A", "doc_path": "L1/design-doc.md"},
            {"id": "L1", "title": "B", "doc_path": "L1b/design-doc.md"},
        ],
    }
    errors = validate_compose_package(pkg)
    assert any("duplicate id" in e for e in errors)


def test_save_and_resolve_focus_doc(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    (rev / "L1").mkdir(parents=True)
    (rev / "L2").mkdir()
    (rev / "L1" / "design-doc.md").write_text("# L1\n", encoding="utf-8")
    (rev / "L2" / "design-doc.md").write_text("# L2\n", encoding="utf-8")
    pkg = build_compose_package(
        profile_id="lulu-design",
        slices=[
            {"id": "L1", "title": "A", "doc_path": "L1/design-doc.md"},
            {"id": "L2", "title": "B", "doc_path": "L2/design-doc.md"},
        ],
    )
    path = save_compose_package(rev, "design-doc.md", pkg)
    assert path.name == "design-package.json"
    loaded = load_compose_package(path)
    assert "order" not in loaded
    assert [s["id"] for s in loaded["slices"]] == ["L1", "L2"]
    assert resolve_focus_doc_path(loaded, "L2", package_path=path) == (
        rev / "L2" / "design-doc.md"
    ).resolve()
    assert is_compose_package_path(path)


def test_missing_slice_docs(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    pkg = build_compose_package(
        profile_id="lulu-design",
        slices=[{"id": "L1", "title": "Only", "doc_path": "L1/design-doc.md"}],
    )
    assert missing_slice_docs(rev, pkg) == ["L1/design-doc.md"]
    with pytest.raises(ValueError, match="missing slice docs"):
        save_compose_package(rev, "design-doc.md", pkg)


def test_chain_ids_from_slices() -> None:
    from compose_package_schema import chain_ids_from_compose_package

    pkg = build_compose_package(
        profile_id="lulu-design",
        slices=[
            {"id": "L1", "title": "A", "doc_path": "L1/design-doc.md"},
            {"id": "L2", "title": "B", "doc_path": "L2/design-doc.md"},
            {"id": "L3", "title": "C", "doc_path": "L3/design-doc.md"},
        ],
    )
    assert chain_ids_from_compose_package(pkg) == ["L1", "L2", "L3"]
