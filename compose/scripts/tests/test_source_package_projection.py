#!/usr/bin/env python3
"""Tests for source-package → scope-package projection."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

import bootstrap  # noqa: F401
from scope_package_projection import (  # noqa: E402
    ScopePackageProjectionError,
    project_source_package_to_scope_slices,
    write_source_package_scope_projection,
)
from scope_package_schema import load_scope_package  # noqa: E402


_SOURCE_SCHEMA = (
    Path(__file__).resolve().parents[3]
    / "lulu-approach"
    / "scripts"
    / "schema"
    / "source_package_schema.py"
)
_spec = importlib.util.spec_from_file_location("source_package_schema", _SOURCE_SCHEMA)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)

build_source_package = _mod.build_source_package
save_source_package = _mod.save_source_package


def _source_package(root: Path, *, commit_status: str = "committed") -> Path:
    for slice_id in ("L1", "L2"):
        source = root / slice_id / "decision-fact.json"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("{}\n", encoding="utf-8")
    package = build_source_package(
        holder_stage="lulu-approach",
        commit_status=commit_status,
        slices=[
            {
                "id": "L1",
                "title": "first",
                "source_path": "L1/decision-fact.json",
                "source_id": "D1",
            },
            {
                "id": "L2",
                "title": "second",
                "source_path": "L2/decision-fact.json",
                "source_id": "D2",
            },
        ],
    )
    return save_source_package(root, package)


def test_projects_each_source_package_slice_to_its_l(tmp_path: Path) -> None:
    package_path = _source_package(tmp_path)
    revision = tmp_path / "revision1"
    revision.mkdir()

    result = write_source_package_scope_projection(
        source_package_path=package_path,
        revision_dir=revision,
    )

    scope = load_scope_package(result)
    assert [row["id"] for row in scope["slices"]] == ["L1", "L2"]
    assert [row["source_id"] for row in scope["slices"]] == ["D1", "D2"]
    assert scope["slices"][1]["source_path"] == str(
        (tmp_path / "L2" / "decision-fact.json").resolve()
    )


def test_rejects_prepared_source_package(tmp_path: Path) -> None:
    package_path = _source_package(tmp_path, commit_status="prepared")
    package = _mod.load_source_package(package_path)

    with pytest.raises(ScopePackageProjectionError, match="commit_status=committed"):
        project_source_package_to_scope_slices(
            package,
            package_root=package_path.parent,
        )
