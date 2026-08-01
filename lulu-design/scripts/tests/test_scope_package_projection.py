#!/usr/bin/env python3
"""Tests for decision-package → scope-package projection (archive-1.0 P3)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import importlib.util

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS_ROOT.parents[1]
_KERNEL_TESTS = _WORKFLOW_ROOT / "compose" / "scripts" / "tests"
_COMPOSE_START = _WORKFLOW_ROOT / "compose" / "scripts" / "start"
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
    norm_refs_from_decision_package,
    project_decision_package_to_scope_slices,
    reject_decision_package_as_scope,
    write_scope_package_projection,
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

_sp_path = (
    _WORKFLOW_ROOT
    / "lulu-approach"
    / "scripts"
    / "schema"
    / "source_package_schema.py"
)
_sp_spec = importlib.util.spec_from_file_location(
    "_p3_test_source_package_schema",
    _sp_path,
)
assert _sp_spec and _sp_spec.loader
_sp_mod = importlib.util.module_from_spec(_sp_spec)
_sp_spec.loader.exec_module(_sp_mod)
build_source_package = _sp_mod.build_source_package
save_source_package = _sp_mod.save_source_package


def _unit_fact(path: Path, text: str = "pick A") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "gates": {
                    "D": [{"id": "D-1", "slot": "D.x", "text": text}],
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _seed_approach_root(tmp_path: Path, *, with_slices: bool) -> Path:
    root = tmp_path / "approach"
    root.mkdir()
    main_fact = _unit_fact(root / "main" / "decision-fact.json", "main pick")
    main_doc = root / "main" / "decision-doc.md"
    main_doc.write_text("# main\n", encoding="utf-8")
    slices: list[dict] = []
    if with_slices:
        for sid, title in (("D1", "slice one"), ("D2", "slice two")):
            fact = _unit_fact(root / sid / "decision-fact.json", title)
            doc = root / sid / "decision-doc.md"
            doc.write_text(f"# {title}\n", encoding="utf-8")
            slices.append(
                {
                    "id": sid,
                    "title": title,
                    "decision_fact_path": f"{sid}/decision-fact.json",
                    "decision_doc_path": f"{sid}/decision-doc.md",
                }
            )
            assert fact.is_file()
    pkg = build_decision_package(
        main={
            "decision_fact_path": "main/decision-fact.json",
            "decision_doc_path": "main/decision-doc.md",
        },
        slices=slices,
    )
    save_decision_package(root, pkg)
    source_slices = [
        {
            "id": "L1",
            "title": "main",
            "source_path": "main/decision-fact.json",
            "source_id": "main",
        }
    ]
    if with_slices:
        source_slices = [
            {
                "id": f"L{index}",
                "title": row["title"],
                "source_path": row["decision_fact_path"],
                "source_id": row["id"],
            }
            for index, row in enumerate(slices, start=1)
        ]
    save_source_package(
        root,
        build_source_package(
            holder_stage="lulu-approach",
            slices=source_slices,
            commit_status="committed",
        ),
    )
    assert main_fact.is_file()
    return root


class TestProjectSlices:
    def test_no_split_projects_main_as_l1(self, tmp_path: Path):
        root = _seed_approach_root(tmp_path, with_slices=False)
        package = json.loads((root / "decision-package.json").read_text(encoding="utf-8"))
        slices = project_decision_package_to_scope_slices(package, approach_root=root)
        assert len(slices) == 1
        assert slices[0]["id"] == "L1"
        assert slices[0]["source_id"] == "main"
        assert slices[0]["source_path"] == str(
            (root / "main" / "decision-fact.json").resolve()
        )

    def test_multi_slice_projects_l1_ln(self, tmp_path: Path):
        root = _seed_approach_root(tmp_path, with_slices=True)
        package = json.loads((root / "decision-package.json").read_text(encoding="utf-8"))
        slices = project_decision_package_to_scope_slices(package, approach_root=root)
        assert [s["id"] for s in slices] == ["L1", "L2"]
        assert [s["source_id"] for s in slices] == ["D1", "D2"]
        assert slices[0]["title"] == "slice one"
        assert slices[1]["source_path"] == str(
            (root / "D2" / "decision-fact.json").resolve()
        )


class TestWriteProjection:
    def test_writes_scope_package_under_revision(self, tmp_path: Path):
        root = _seed_approach_root(tmp_path, with_slices=False)
        rev = tmp_path / "design" / "revision1"
        rev.mkdir(parents=True)
        out = write_scope_package_projection(
            decision_package_path=root / "decision-package.json",
            revision_dir=rev,
        )
        assert out == rev / "scope-package.json"
        loaded = load_scope_package(out)
        assert loaded["slices"][0]["source_id"] == "main"

    def test_rejects_same_revision_rebuild(self, tmp_path: Path):
        root = _seed_approach_root(tmp_path, with_slices=True)
        rev = tmp_path / "revision1"
        rev.mkdir()
        write_scope_package_projection(
            decision_package_path=root / "decision-package.json",
            revision_dir=rev,
        )
        with pytest.raises(ScopePackageProjectionError, match="no same-revision rebuild"):
            write_scope_package_projection(
                decision_package_path=root / "decision-package.json",
                revision_dir=rev,
            )


class TestRejectDecisionPackageAsScope:
    def test_reject_helper(self, tmp_path: Path):
        pkg = tmp_path / "decision-package.json"
        pkg.write_text("{}", encoding="utf-8")
        with pytest.raises(ScopePackageProjectionError, match="must not be used"):
            reject_decision_package_as_scope(pkg)

class TestNormKinds:
    def test_make_norm_ref_requires_closed_kind(self, tmp_path: Path):
        p = tmp_path / "x.md"
        p.write_text("x\n", encoding="utf-8")
        for kind in sorted(NORM_KINDS):
            ref = make_norm_ref(delivered_type="lulu-approach", path=str(p), kind=kind)
            assert ref.kind == kind
        with pytest.raises(ScopePackageProjectionError, match="norm kind"):
            make_norm_ref(delivered_type="lulu-approach", path=str(p), kind="bogus")

    def test_norm_refs_include_parent_and_split(self, tmp_path: Path):
        root = _seed_approach_root(tmp_path, with_slices=True)
        (root / "dependency-tree.json").write_text('{"version":1}\n', encoding="utf-8")
        (root / "decision-rulers.json").write_text("{}\n", encoding="utf-8")
        refs = norm_refs_from_decision_package(
            decision_package_path=root / "decision-package.json",
        )
        kinds = {r.kind for r in refs}
        assert "parent_decision" in kinds
        assert "split_artifact" in kinds
        assert all(r.kind in NORM_KINDS for r in refs)


class TestAdapterProjection:
    def test_adapter_no_split_writes_scope_package(self, tmp_path: Path):
        root = _seed_approach_root(tmp_path, with_slices=False)
        rev = tmp_path / "revision1"
        rev.mkdir()
        adapter = TechDesignStartAdapter()
        refs = adapter.resolve_scope_refs(
            delivered_refs=[
                DeliveredRef(
                    type="lulu-approach",
                    path=str((root / "source-package.json").resolve()),
                    artifact="source-package",
                )
            ],
            revision_dir=rev,
        )
        assert len(refs) == 1
        assert Path(refs[0].path).name == "scope-package.json"
        assert (rev / "scope-package.json").is_file()
        loaded = load_scope_package(Path(refs[0].path))
        assert loaded["slices"][0]["source_id"] == "main"

    def test_adapter_multi_slice_and_path_detection(self, tmp_path: Path):
        root = _seed_approach_root(tmp_path, with_slices=True)
        rev = tmp_path / "revision1"
        rev.mkdir()
        adapter = TechDesignStartAdapter()
        # path ends with source-package.json (no artifact) still projects
        refs = adapter.resolve_scope_refs(
            delivered_refs=[
                DeliveredRef(
                    type="lulu-approach",
                    path=str((root / "source-package.json").resolve()),
                )
            ],
            revision_dir=rev,
        )
        loaded = load_scope_package(Path(refs[0].path))
        assert [s["id"] for s in loaded["slices"]] == ["L1", "L2"]

    def test_adapter_requires_revision_dir_for_package(self, tmp_path: Path):
        root = _seed_approach_root(tmp_path, with_slices=False)
        adapter = TechDesignStartAdapter()
        with pytest.raises(ValueError, match="revision_dir required"):
            adapter.resolve_scope_refs(
                delivered_refs=[
                    DeliveredRef(
                        type="lulu-approach",
                        path=str((root / "source-package.json").resolve()),
                        artifact="source-package",
                    )
                ],
            )

    def test_adapter_requires_committed_source_package(self, tmp_path: Path):
        adapter = TechDesignStartAdapter()
        with pytest.raises(ValueError, match="committed source-package"):
            adapter.resolve_scope_refs(
                delivered_refs=[
                    DeliveredRef(
                        type="lulu-approach",
                        path=str(tmp_path / "decision-doc.md"),
                    )
                ],
            )

    def test_adapter_norm_from_package(self, tmp_path: Path):
        root = _seed_approach_root(tmp_path, with_slices=False)
        (root / "dependency-tree.json").write_text("{}\n", encoding="utf-8")
        adapter = TechDesignStartAdapter()
        norms = adapter.resolve_norm_constraint_refs(
            cycle_id="feat-x",
            project_root=tmp_path,
            delivered_refs=[
                DeliveredRef(
                    type="lulu-approach",
                    path=str((root / "source-package.json").resolve()),
                    artifact="source-package",
                )
            ],
        )
        assert any(r.kind == "parent_decision" for r in norms)
        assert any(r.kind == "split_artifact" for r in norms)
