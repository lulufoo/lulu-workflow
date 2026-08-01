#!/usr/bin/env python3
"""Tests for TechDesignStartAdapter — validate_for_start, resolve_delivered_refs, resolve_scope_refs."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS_ROOT.parents[1]
_KERNEL_TESTS = _WORKFLOW_ROOT / "compose" / "scripts" / "tests"
_START = _SCRIPTS_ROOT / "start"
for _p in (_KERNEL_TESTS, _START):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bootstrap  # noqa: F401
from delivered_refs_schema import record_delivered_ref  # noqa: E402
from tech_design_start_adapter import TechDesignStartAdapter  # noqa: E402

_CYCLE = "feat-design-start"
_ADAPTER = TechDesignStartAdapter()

_dp_path = (
    _WORKFLOW_ROOT
    / "lulu-approach"
    / "scripts"
    / "schema"
    / "decision_package_schema.py"
)
_dp_spec = importlib.util.spec_from_file_location(
    "_tech_design_start_dp_schema",
    _dp_path,
)
assert _dp_spec and _dp_spec.loader
_dp_mod = importlib.util.module_from_spec(_dp_spec)
_dp_spec.loader.exec_module(_dp_mod)
build_decision_package = _dp_mod.build_decision_package
save_decision_package = _dp_mod.save_decision_package


def _write_file(tmp_path: Path, rel: str, content: str = "# stub\n") -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _seed_decision_package(tmp_path: Path) -> Path:
    """Write approach-internal artifacts and one decision package."""
    root = tmp_path / "approach"
    (root / "main").mkdir(parents=True)
    fact = root / "main" / "decision-fact.json"
    fact.write_text(
        json.dumps(
            {
                "version": 1,
                "gates": {
                    "D": [{"id": "D-1", "slot": "D.x", "text": "pick A"}],
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "main" / "decision-doc.md").write_text("# main\n", encoding="utf-8")
    return save_decision_package(
        root,
        build_decision_package(
            main={
                "decision_fact_path": "main/decision-fact.json",
                "decision_doc_path": "main/decision-doc.md",
            },
            slices=[],
        ),
    )


def _seed_diag_ref(tmp_path: Path, cycle_id: str) -> Path:
    pkg = _seed_decision_package(tmp_path)
    record_delivered_ref(
        cycle_id,
        tmp_path,
        delivered_type="lulu-approach",
        path=str(pkg.resolve()),
        revision=1,
        profile_id="lulu-approach",
        source_workflow_state=str(pkg.resolve()),
        artifact="decision-package",
    )
    return pkg


def _seed_product_ref(tmp_path: Path, cycle_id: str) -> Path:
    doc = _write_file(tmp_path, "spec/lulu-spec.md")
    record_delivered_ref(
        cycle_id,
        tmp_path,
        delivered_type="lulu-spec",
        path=str(doc.resolve()),
        revision=1,
        profile_id="lulu-spec",
        source_workflow_state=str(doc.resolve()),
    )
    return doc


class TestValidateForStart:
    def test_tech_mode_requires_tech_diagnostic(self, tmp_path: Path):
        errors = _ADAPTER.validate_for_start(_CYCLE, tmp_path, run_mode="tech")
        assert any("lulu-approach" in e for e in errors)

    def test_tech_mode_ok_with_diag(self, tmp_path: Path):
        _seed_diag_ref(tmp_path, _CYCLE)
        errors = _ADAPTER.validate_for_start(_CYCLE, tmp_path, run_mode="tech")
        assert errors == []

    def test_tech_mode_rejects_source_package(self, tmp_path: Path):
        root = tmp_path / "approach"
        root.mkdir()
        package = root / "source-package.json"
        package.write_text("{}", encoding="utf-8")
        record_delivered_ref(
            _CYCLE,
            tmp_path,
            delivered_type="lulu-approach",
            path=str(package.resolve()),
            revision=1,
            profile_id="lulu-approach",
            source_workflow_state=str(package.resolve()),
            artifact="source-package",
        )
        errors = _ADAPTER.validate_for_start(_CYCLE, tmp_path, run_mode="tech")
        assert errors == [
            "lulu-approach must deliver a decision-package.json "
            "(artifact=decision-package)"
        ]

    def test_product_mode_requires_both_refs(self, tmp_path: Path):
        _seed_diag_ref(tmp_path, _CYCLE)
        errors = _ADAPTER.validate_for_start(_CYCLE, tmp_path, run_mode="product")
        assert any("lulu-spec" in e for e in errors)

    def test_product_mode_ok_with_both_refs(self, tmp_path: Path):
        _seed_diag_ref(tmp_path, _CYCLE)
        _seed_product_ref(tmp_path, _CYCLE)
        errors = _ADAPTER.validate_for_start(_CYCLE, tmp_path, run_mode="product")
        assert errors == []


class TestInferRunMode:
    def test_tech_when_no_spec(self, tmp_path: Path):
        _seed_diag_ref(tmp_path, _CYCLE)
        assert _ADAPTER.infer_run_mode(_CYCLE, tmp_path) == "tech"

    def test_product_when_spec_present(self, tmp_path: Path):
        _seed_diag_ref(tmp_path, _CYCLE)
        _seed_product_ref(tmp_path, _CYCLE)
        assert _ADAPTER.infer_run_mode(_CYCLE, tmp_path) == "product"

    def test_tech_when_spec_path_missing(self, tmp_path: Path):
        _seed_diag_ref(tmp_path, _CYCLE)
        record_delivered_ref(
            _CYCLE,
            tmp_path,
            delivered_type="lulu-spec",
            path="/nonexistent/product-doc.md",
            revision=1,
            profile_id="lulu-spec",
            source_workflow_state="/nonexistent/ws.md",
        )
        assert _ADAPTER.infer_run_mode(_CYCLE, tmp_path) == "tech"


class TestResolveDeliveredRefs:
    def test_tech_mode_returns_diag_only(self, tmp_path: Path):
        diag = _seed_diag_ref(tmp_path, _CYCLE)
        _seed_product_ref(tmp_path, _CYCLE)
        refs = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        types = [r.type for r in refs]
        assert types == ["lulu-approach"]
        assert refs[0].path == str(diag.resolve())

    def test_product_mode_returns_diag_and_product(self, tmp_path: Path):
        _seed_diag_ref(tmp_path, _CYCLE)
        _seed_product_ref(tmp_path, _CYCLE)
        refs = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="product")
        types = [r.type for r in refs]
        assert "lulu-approach" in types
        assert "lulu-spec" in types
        assert len(refs) == 2

    def test_missing_file_excluded(self, tmp_path: Path):
        record_delivered_ref(
            _CYCLE,
            tmp_path,
            delivered_type="lulu-approach",
            path="/nonexistent/decision-doc.md",
            revision=1,
            profile_id="lulu-approach",
            source_workflow_state="/nonexistent/ws.md",
        )
        refs = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        assert refs == []


class TestResolveScopeRefs:
    def test_tech_mode_scope_is_scope_package(self, tmp_path: Path):
        diag = _seed_diag_ref(tmp_path, _CYCLE)
        spec = _seed_product_ref(tmp_path, _CYCLE)
        from delivered_refs_schema import DeliveredRef  # noqa: WPS433

        rev = tmp_path / "design" / "revision1"
        rev.mkdir(parents=True)
        all_refs = [
            DeliveredRef(
                type="lulu-approach",
                path=str(diag.resolve()),
                artifact="decision-package",
            ),
            DeliveredRef(type="lulu-spec", path=str(spec.resolve())),
        ]
        scope = _ADAPTER.resolve_scope_refs(
            delivered_refs=all_refs,
            run_mode="tech",
            revision_dir=rev,
        )
        assert [r.type for r in scope] == ["lulu-approach"]
        assert scope[0].artifact == "scope-package"
        assert Path(scope[0].path).name == "scope-package.json"

    def test_product_mode_scope_is_scope_package(self, tmp_path: Path):
        diag = _seed_diag_ref(tmp_path, _CYCLE)
        spec = _seed_product_ref(tmp_path, _CYCLE)
        from delivered_refs_schema import DeliveredRef  # noqa: WPS433

        rev = tmp_path / "design" / "revision2"
        rev.mkdir(parents=True)
        all_refs = [
            DeliveredRef(
                type="lulu-approach",
                path=str(diag.resolve()),
                artifact="decision-package",
            ),
            DeliveredRef(type="lulu-spec", path=str(spec.resolve())),
        ]
        scope = _ADAPTER.resolve_scope_refs(
            delivered_refs=all_refs,
            run_mode="product",
            revision_dir=rev,
        )
        assert [r.type for r in scope] == ["lulu-approach"]
        assert scope[0].artifact == "scope-package"

    def test_scope_requires_decision_package(self, tmp_path: Path):
        from delivered_refs_schema import DeliveredRef  # noqa: WPS433

        with pytest.raises(ValueError, match="decision-package"):
            _ADAPTER.resolve_scope_refs(
                delivered_refs=[
                    DeliveredRef(
                        type="lulu-approach",
                        path=str(tmp_path / "decision-doc.md"),
                    ),
                ],
            )

    def test_product_mode_intent_baseline_is_spec(self, tmp_path: Path):
        diag = _seed_diag_ref(tmp_path, _CYCLE)
        spec = _seed_product_ref(tmp_path, _CYCLE)
        from delivered_refs_schema import DeliveredRef  # noqa: WPS433

        all_refs = [
            DeliveredRef(type="lulu-approach", path=str(diag.resolve())),
            DeliveredRef(type="lulu-spec", path=str(spec.resolve())),
        ]
        baseline = _ADAPTER.resolve_intent_baseline_refs(
            delivered_refs=all_refs,
            run_mode="product",
        )
        assert [r.type for r in baseline] == ["lulu-spec"]


    def test_product_mode_intent_baseline_empty_in_tech_mode(self, tmp_path: Path):
        diag = _seed_diag_ref(tmp_path, _CYCLE)
        spec = _seed_product_ref(tmp_path, _CYCLE)
        from delivered_refs_schema import DeliveredRef  # noqa: WPS433

        all_refs = [
            DeliveredRef(type="lulu-approach", path=str(diag.resolve())),
            DeliveredRef(type="lulu-spec", path=str(spec.resolve())),
        ]
        baseline = _ADAPTER.resolve_intent_baseline_refs(
            delivered_refs=all_refs,
            run_mode="tech",
        )
        assert baseline == []


class TestPostStartGuidance:
    def test_tech_mode_mentions_d1_d2(self):
        from delivered_refs_schema import DeliveredRef  # noqa: WPS433

        msg = _ADAPTER.post_start_guidance(
            run_mode="tech",
            carry_forward_ref="",
            scope_refs=[DeliveredRef(type="lulu-approach", path="/d.md")],
        )
        assert "d1" in msg
        assert "d2" in msg
        assert "d3" not in msg

    def test_product_mode_mentions_d3(self):
        msg = _ADAPTER.post_start_guidance(
            run_mode="product",
            carry_forward_ref="",
            scope_refs=[],
        )
        assert "d3" in msg
