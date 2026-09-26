#!/usr/bin/env python3
"""Tests for decision-package → scope-package projection."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS_ROOT.parents[1]
_KERNEL_TESTS = _WORKFLOW_ROOT / "compose" / "scripts" / "tests"
_COMPOSE_START = _WORKFLOW_ROOT / "compose" / "scripts" / "scope"
_DESIGN_START = _SCRIPTS_ROOT / "start"
for _p in (_KERNEL_TESTS, _COMPOSE_START, _DESIGN_START):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bootstrap  # noqa: F401
from delivered_refs_schema import DeliveredRef  # noqa: E402
from scope_package_projection import (  # noqa: E402
    NORM_KINDS,
    ScopePackageProjectionError,
    make_norm_ref,
    reject_non_scope_package,
    write_scope_package_from_source,
)
from scope_package_schema import load_scope_package  # noqa: E402
from tech_design_start_adapter import TechDesignStartAdapter  # noqa: E402

_dp_path = (
    _WORKFLOW_ROOT
    / "lulu-approach"
    / "scripts"
    / "schema"
    / "decision_package_schema.py"
)
_dp_spec = importlib.util.spec_from_file_location(
    "_p3_test_decision_package_schema",
    _dp_path,
)
assert _dp_spec and _dp_spec.loader
_dp_mod = importlib.util.module_from_spec(_dp_spec)
_dp_spec.loader.exec_module(_dp_mod)
build_decision_package = _dp_mod.build_decision_package
save_decision_package = _dp_mod.save_decision_package


def _seed_approach_root(tmp_path: Path) -> Path:
    root = tmp_path / "approach"
    root.mkdir()
    main_doc = root / "decision-doc.md"
    main_doc.write_text("# main\n", encoding="utf-8")
    save_decision_package(
        root,
        build_decision_package(main={"decision_doc_path": "decision-doc.md"}),
    )
    return root


class TestWriteProjection:
    def test_writes_scope_package_from_source(self, tmp_path: Path):
        src = tmp_path / "decision-doc.md"
        src.write_text("# main\n", encoding="utf-8")
        rev = tmp_path / "design" / "revision1"
        rev.mkdir(parents=True)
        out = write_scope_package_from_source(source_path=src, output_dir=rev)
        assert out == rev / "scope-package.json"
        loaded = load_scope_package(out)
        assert loaded["source_path"] == str(src.resolve())
        assert "slices" not in loaded

    def test_rejects_same_dir_rebuild(self, tmp_path: Path):
        src = tmp_path / "decision-doc.md"
        src.write_text("# main\n", encoding="utf-8")
        rev = tmp_path / "revision1"
        rev.mkdir()
        write_scope_package_from_source(source_path=src, output_dir=rev)
        with pytest.raises(ScopePackageProjectionError, match="no same-dir rebuild"):
            write_scope_package_from_source(source_path=src, output_dir=rev)


class TestRejectNonScopePackage:
    def test_reject_helper(self, tmp_path: Path):
        pkg = tmp_path / "decision-package.json"
        pkg.write_text("{}\n", encoding="utf-8")
        with pytest.raises(ScopePackageProjectionError, match="scope-package"):
            reject_non_scope_package(pkg)


class TestNormKinds:
    def test_make_norm_ref_requires_closed_kind(self, tmp_path: Path):
        p = tmp_path / "x.md"
        p.write_text("x\n", encoding="utf-8")
        for kind in sorted(NORM_KINDS):
            ref = make_norm_ref(delivered_type="lulu-approach", path=str(p), kind=kind)
            assert ref.kind == kind
        with pytest.raises(ScopePackageProjectionError, match="norm kind"):
            make_norm_ref(delivered_type="lulu-approach", path=str(p), kind="bogus")


class TestAdapterProjection:
    def test_adapter_writes_scope_package(self, tmp_path: Path):
        root = _seed_approach_root(tmp_path)
        rev = tmp_path / "revision1"
        rev.mkdir()
        adapter = TechDesignStartAdapter()
        refs = adapter.resolve_scope_refs(
            delivered_refs=[
                DeliveredRef(
                    type="lulu-approach",
                    path=str((root / "decision-package.json").resolve()),
                    artifact="decision-package",
                )
            ],
            revision_dir=rev,
        )
        assert len(refs) == 1
        assert Path(refs[0].path).name == "scope-package.json"
        loaded = load_scope_package(Path(refs[0].path))
        assert loaded["source_path"] == str((root / "decision-doc.md").resolve())
        assert "slices" not in loaded

    def test_adapter_requires_output_dir(self, tmp_path: Path):
        root = _seed_approach_root(tmp_path)
        adapter = TechDesignStartAdapter()
        with pytest.raises(ValueError, match="output_dir required"):
            adapter.resolve_scope_refs(
                delivered_refs=[
                    DeliveredRef(
                        type="lulu-approach",
                        path=str((root / "decision-package.json").resolve()),
                        artifact="decision-package",
                    )
                ],
            )

    def test_adapter_requires_decision_package(self, tmp_path: Path):
        adapter = TechDesignStartAdapter()
        with pytest.raises(ValueError, match="decision-package"):
            adapter.resolve_scope_refs(
                delivered_refs=[
                    DeliveredRef(
                        type="lulu-approach",
                        path=str(tmp_path / "decision-doc.md"),
                    )
                ],
            )

    def test_adapter_norm_ignores_decision_package(self, tmp_path: Path):
        root = _seed_approach_root(tmp_path)
        adapter = TechDesignStartAdapter()
        norms = adapter.resolve_norm_constraint_refs(
            cycle_id="feat-x",
            project_root=tmp_path,
            delivered_refs=[
                DeliveredRef(
                    type="lulu-approach",
                    path=str((root / "decision-package.json").resolve()),
                    artifact="decision-package",
                )
            ],
        )
        kinds = {getattr(ref, "kind", None) for ref in norms}
        assert "parent_decision" not in kinds
        assert "split_artifact" not in kinds
        assert norms == []
