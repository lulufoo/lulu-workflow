#!/usr/bin/env python3
"""Tests for scope_refs snapshot and StartAdapter.resolve_scope_refs."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
for _rel in (
    "compose/scripts/start",
    "lulu-plan/scripts/start",
    "lulu-design/scripts/start",
    "lulu-spec/scripts/start",
    "lulu-arch/scripts/start",
    "lulu-blueprint/scripts/start",
    "decision/scripts",
):
    _p = _WORKFLOW_ROOT / _rel
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bootstrap  # noqa: F401
from delivered_refs_schema import DeliveredRef  # noqa: E402
from product_blueprint_start_adapter import ProductBlueprintStartAdapter  # noqa: E402
from product_spec_start_adapter import ProductSpecStartAdapter  # noqa: E402
from tech_arch_start_adapter import TechArchStartAdapter  # noqa: E402
from tech_design_start_adapter import TechDesignStartAdapter  # noqa: E402
from tech_plan_start_adapter import TechPlanStartAdapter  # noqa: E402

_dp_path = (
    _WORKFLOW_ROOT
    / "lulu-approach"
    / "scripts"
    / "schema"
    / "decision_package_schema.py"
)
_dp_spec = importlib.util.spec_from_file_location("_dp_schema_scope_tests", _dp_path)
assert _dp_spec and _dp_spec.loader
_dp_mod = importlib.util.module_from_spec(_dp_spec)
_dp_spec.loader.exec_module(_dp_mod)
build_decision_package = _dp_mod.build_decision_package
save_decision_package = _dp_mod.save_decision_package


def _unit_fact(tmp_path: Path, name: str = "decision-fact.json") -> Path:
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
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
    return path


def _design_package(tmp_path: Path) -> Path:
    from compose_package_schema import build_compose_package, save_compose_package

    revision = tmp_path / "design" / "revision1"
    (revision / "L1").mkdir(parents=True)
    (revision / "L1" / "design-doc.md").write_text("# Design\n", encoding="utf-8")
    return save_compose_package(
        revision,
        "design-doc.md",
        build_compose_package(
            profile_id="lulu-design",
            slices=[{"id": "L1", "title": "Design", "doc_path": "L1/design-doc.md"}],
        ),
    )


def _write_approach_decision_package(approach_root: Path) -> Path:
    approach_root.mkdir(parents=True, exist_ok=True)
    (approach_root / "main").mkdir(parents=True, exist_ok=True)
    fact = _unit_fact(approach_root / "main", "decision-fact.json")
    del fact
    (approach_root / "main" / "decision-doc.md").write_text("# main\n", encoding="utf-8")
    return save_decision_package(
        approach_root,
        build_decision_package(
            main={
                "decision_fact_path": "main/decision-fact.json",
                "decision_doc_path": "main/decision-doc.md",
            },
            slices=[],
        ),
    )


def _write_bet_decision_package(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _unit_fact(root, "decision-fact.json")
    (root / "decision-doc.md").write_text("# Decision\n", encoding="utf-8")
    return save_decision_package(
        root,
        build_decision_package(
            main={
                "decision_fact_path": "decision-fact.json",
                "decision_doc_path": "decision-doc.md",
            },
            slices=[],
        ),
    )


def test_tech_plan_resolve_scope_refs_primary_tech_chain(tmp_path: Path):
    adapter = TechPlanStartAdapter()
    design_package = _design_package(tmp_path)
    revision = tmp_path / "plan" / "revision1"
    revision.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(type="lulu-approach", path="/abs/decision.md"),
            DeliveredRef(type="lulu-design", path=str(design_package)),
        ],
        run_mode="tech",
        revision_dir=revision,
    )
    assert len(refs) == 1
    assert refs[0].type == "lulu-design"
    assert refs[0].artifact == "scope-package"
    assert Path(refs[0].path) == revision / "scope-package.json"


def test_tech_plan_approach_only_requires_decision_package(tmp_path: Path):
    """Plan←approach requires a decision package."""
    adapter = TechPlanStartAdapter()
    with pytest.raises(ValueError, match="decision-package"):
        adapter.resolve_scope_refs(
            delivered_refs=[
                DeliveredRef(type="lulu-approach", path="/abs/decision.md"),
                DeliveredRef(type="lulu-spec", path="/abs/product.md"),
            ],
            run_mode="product",
        )

    decision_package = _write_approach_decision_package(tmp_path / "approach")
    rev = tmp_path / "plan" / "revision1"
    rev.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str(decision_package.resolve()),
                artifact="decision-package",
            ),
            DeliveredRef(type="lulu-spec", path="/abs/product.md"),
        ],
        run_mode="product",
        revision_dir=rev,
    )
    assert refs[0].type == "lulu-approach"
    assert refs[0].artifact == "scope-package"
    assert Path(refs[0].path).name == "scope-package.json"
    assert (rev / "scope-package.json").is_file()


def test_tech_design_resolve_scope_refs_requires_decision_package(tmp_path: Path):
    """Design start requires a decision package."""
    adapter = TechDesignStartAdapter()
    with pytest.raises(ValueError, match="decision-package"):
        adapter.resolve_scope_refs(
            delivered_refs=[DeliveredRef(type="lulu-approach", path="/abs/decision.md")],
            run_mode="tech",
        )

    decision_package = _write_approach_decision_package(tmp_path / "approach")
    rev = tmp_path / "design" / "revision1"
    rev.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str(decision_package.resolve()),
                artifact="decision-package",
            ),
        ],
        run_mode="tech",
        revision_dir=rev,
    )
    assert len(refs) == 1
    assert refs[0].artifact == "scope-package"
    assert Path(refs[0].path).name == "scope-package.json"


def test_product_spec_projects_bet_decision_package(tmp_path: Path):
    adapter = ProductSpecStartAdapter()
    decision = _write_bet_decision_package(tmp_path / "bet")
    revision = tmp_path / "spec" / "revision1"
    revision.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-bet",
                path=str(decision),
                artifact="decision-package",
            ),
        ],
        run_mode="product",
        revision_dir=revision,
    )
    assert refs[0].type == "lulu-bet"
    assert refs[0].artifact == "scope-package"
    assert Path(refs[0].path) == revision / "scope-package.json"


def test_delivered_ref_ignores_legacy_decision_fact_path_key() -> None:
    """Compose DeliveredRef must not surface cycle audit key decision_fact_path."""
    from delivered_refs_schema import ref_from_file_entry

    data = {
        "entries": {
            "lulu-bet": {
                "path": "/abs/decision-package.json",
                "decision_fact_path": "/abs/decision-fact.json",
                "artifact": "decision-package",
            }
        }
    }
    ref = ref_from_file_entry("lulu-bet", data)
    assert ref is not None
    assert ref.path == "/abs/decision-package.json"
    assert ref.artifact == "decision-package"
    assert "decision_fact_path" not in ref.to_dict()
    assert not hasattr(ref, "decision_fact_path")


def test_tech_arch_projects_approach_decision_package(tmp_path: Path):
    adapter = TechArchStartAdapter()
    decision = _write_approach_decision_package(tmp_path / "approach")
    revision = tmp_path / "arch" / "revision1"
    revision.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str(decision),
                artifact="decision-package",
            ),
        ],
        revision_dir=revision,
    )
    assert refs[0].artifact == "scope-package"
    assert Path(refs[0].path) == revision / "scope-package.json"


def test_product_blueprint_projects_bet_decision_package(tmp_path: Path):
    adapter = ProductBlueprintStartAdapter()
    decision = _write_bet_decision_package(tmp_path / "bet")
    revision = tmp_path / "blueprint" / "revision1"
    revision.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-bet",
                path=str(decision),
                artifact="decision-package",
            ),
        ],
        revision_dir=revision,
    )
    assert refs[0].artifact == "scope-package"
    assert Path(refs[0].path) == revision / "scope-package.json"


def test_tech_plan_approach_fallback_projects_decision_package(tmp_path: Path):
    adapter = TechPlanStartAdapter()
    decision_package = _write_approach_decision_package(tmp_path / "approach")
    rev = tmp_path / "plan" / "revision1"
    rev.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str(decision_package.resolve()),
                artifact="decision-package",
            ),
        ],
        revision_dir=rev,
    )
    assert refs[0].type == "lulu-approach"
    assert refs[0].artifact == "scope-package"
    assert Path(refs[0].path).name == "scope-package.json"


def test_tech_plan_design_primary_projects_design_doc_path(tmp_path: Path):
    adapter = TechPlanStartAdapter()
    design_package = _design_package(tmp_path)
    revision = tmp_path / "plan" / "revision1"
    revision.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(type="lulu-approach", path="/abs/decision.md"),
            DeliveredRef(type="lulu-design", path=str(design_package)),
        ],
        revision_dir=revision,
    )
    assert refs[0].type == "lulu-design"
    assert refs[0].artifact == "scope-package"
    scope = json.loads((revision / "scope-package.json").read_text(encoding="utf-8"))
    assert scope["slices"][0]["source_path"] == str(
        (design_package.parent / "L1" / "design-doc.md").resolve()
    )


def test_tech_design_scope_excludes_spec_in_product_mode(tmp_path: Path):
    adapter = TechDesignStartAdapter()
    decision_package = _write_approach_decision_package(tmp_path / "approach")
    rev = tmp_path / "design" / "revision1"
    rev.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str(decision_package.resolve()),
                artifact="decision-package",
            ),
            DeliveredRef(type="lulu-spec", path="/abs/product.md"),
        ],
        run_mode="product",
        revision_dir=rev,
    )
    assert [r.type for r in refs] == ["lulu-approach"]
    assert refs[0].artifact == "scope-package"
    assert Path(refs[0].path).name == "scope-package.json"


def test_tech_design_intent_baseline_is_spec_when_present():
    adapter = TechDesignStartAdapter()
    refs = adapter.resolve_intent_baseline_refs(
        delivered_refs=[
            DeliveredRef(type="lulu-approach", path="/abs/decision.md"),
            DeliveredRef(type="lulu-spec", path="/abs/product.md"),
        ],
        run_mode="product",
    )
    assert [r.type for r in refs] == ["lulu-spec"]


def test_tech_design_intent_baseline_empty_without_spec():
    adapter = TechDesignStartAdapter()
    refs = adapter.resolve_intent_baseline_refs(
        delivered_refs=[DeliveredRef(type="lulu-approach", path="/abs/decision.md")],
    )
    assert refs == []


def test_tech_design_infer_run_mode():
    adapter = TechDesignStartAdapter()
    assert adapter.infer_run_mode.__name__ == "infer_run_mode"


def test_tech_plan_infer_run_mode():
    adapter = TechPlanStartAdapter()
    assert adapter.infer_run_mode.__name__ == "infer_run_mode"


def test_tech_plan_has_no_resolve_scope_facts_ref():
    adapter = TechPlanStartAdapter()
    assert not hasattr(adapter, "resolve_scope_facts_ref")


def test_product_spec_infer_run_mode():
    adapter = ProductSpecStartAdapter()
    assert adapter.infer_run_mode("feat-x", Path("/tmp")) == "product"


def test_tech_design_norm_constraint_empty():
    adapter = TechDesignStartAdapter()
    assert adapter.resolve_norm_constraint_refs(cycle_id="feat-x") == []
