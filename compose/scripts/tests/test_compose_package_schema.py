#!/usr/bin/env python3
"""Tests for compose_package_schema v2 (single doc_path)."""

from __future__ import annotations

from pathlib import Path

import bootstrap  # noqa: F401
import pytest
from compose_package_schema import (  # noqa: E402
    build_compose_package,
    is_compose_package_path,
    load_compose_package,
    missing_doc,
    package_doc_path,
    package_filename_from_doc,
    save_compose_package,
    validate_compose_package,
)


def test_package_filename_from_doc() -> None:
    assert package_filename_from_doc("design-doc.md") == "design-package.json"
    assert package_filename_from_doc("tech-doc.md") == "tech-package.json"
    assert package_filename_from_doc("product-doc.md") == "product-package.json"


def test_build_single_doc() -> None:
    pkg = build_compose_package(
        profile_id="lulu-design",
        doc_path="execution/design-doc.md",
    )
    assert pkg == {
        "version": 2,
        "profile_id": "lulu-design",
        "doc_path": "execution/design-doc.md",
    }
    assert validate_compose_package(pkg) == []


def test_validate_rejects_slices() -> None:
    pkg = build_compose_package(
        profile_id="lulu-design",
        doc_path="execution/design-doc.md",
    )
    pkg["slices"] = []
    errors = validate_compose_package(pkg)
    assert any("unknown keys" in e for e in errors)


def test_save_and_resolve_doc(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    (rev / "execution").mkdir(parents=True)
    (rev / "execution" / "design-doc.md").write_text("# design\n", encoding="utf-8")
    pkg = build_compose_package(
        profile_id="lulu-design",
        doc_path="execution/design-doc.md",
    )
    path = save_compose_package(rev, "design-doc.md", pkg)
    assert path.name == "design-package.json"
    loaded = load_compose_package(path)
    assert loaded["doc_path"] == "execution/design-doc.md"
    assert package_doc_path(loaded, package_path=path) == (
        rev / "execution" / "design-doc.md"
    ).resolve()
    assert is_compose_package_path(path)


def test_missing_doc(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    pkg = build_compose_package(
        profile_id="lulu-design",
        doc_path="execution/design-doc.md",
    )
    assert missing_doc(rev, pkg) == "execution/design-doc.md"
    with pytest.raises(ValueError, match="missing doc"):
        save_compose_package(rev, "design-doc.md", pkg)
