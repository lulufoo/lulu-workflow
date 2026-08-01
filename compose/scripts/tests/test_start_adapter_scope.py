#!/usr/bin/env python3
"""Tests for scope_refs snapshot and StartAdapter.resolve_scope_refs."""

from __future__ import annotations

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
from dec_source_package_schema import (  # noqa: E402
    build_source_package,
    save_source_package,
)
from product_blueprint_start_adapter import ProductBlueprintStartAdapter  # noqa: E402
from product_spec_start_adapter import ProductSpecStartAdapter  # noqa: E402
from tech_arch_start_adapter import TechArchStartAdapter  # noqa: E402
from tech_design_start_adapter import TechDesignStartAdapter  # noqa: E402
from tech_plan_start_adapter import TechPlanStartAdapter  # noqa: E402


def _unit_fact(tmp_path: Path, name: str = "decision-fact.json") -> Path:
    path = tmp_path / name
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


def _write_approach_source_package(approach_root: Path) -> Path:
    import importlib.util

    schema_path = (
        _WORKFLOW_ROOT
        / "lulu-approach"
        / "scripts"
        / "schema"
        / "source_package_schema.py"
    )
    spec = importlib.util.spec_from_file_location("_source_package_schema", schema_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.save_source_package(
        approach_root,
        mod.build_source_package(
            holder_stage="lulu-approach",
            commit_status="committed",
            slices=[
                {
                    "id": "L1",
                    "title": "main",
                    "source_path": "main/decision-fact.json",
                    "source_id": "main",
                }
            ],
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


def test_tech_plan_approach_only_requires_source_package(tmp_path: Path):
    """Plan←approach requires a committed source package."""
    import importlib.util

    adapter = TechPlanStartAdapter()
    with pytest.raises(ValueError, match="committed source-package"):
        adapter.resolve_scope_refs(
            delivered_refs=[
                DeliveredRef(type="lulu-approach", path="/abs/decision.md"),
                DeliveredRef(type="lulu-spec", path="/abs/product.md"),
            ],
            run_mode="product",
        )

    approach = tmp_path / "approach"
    fact = _unit_fact(tmp_path)
    (approach / "main").mkdir(parents=True)
    main_fact = approach / "main" / "decision-fact.json"
    main_fact.write_text(fact.read_text(encoding="utf-8"), encoding="utf-8")
    (approach / "main" / "decision-doc.md").write_text("# main\n", encoding="utf-8")
    dp_path = (
        _WORKFLOW_ROOT
        / "lulu-approach"
        / "scripts"
        / "schema"
        / "decision_package_schema.py"
    )
    spec = importlib.util.spec_from_file_location("_dp_schema_plan_scope", dp_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.save_decision_package(
        approach,
        mod.build_decision_package(
            main={
                "decision_fact_path": "main/decision-fact.json",
                "decision_doc_path": "main/decision-doc.md",
            },
            slices=[],
        ),
    )
    source_package = _write_approach_source_package(approach)
    rev = tmp_path / "plan" / "revision1"
    rev.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str(source_package.resolve()),
                artifact="source-package",
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


def test_tech_design_resolve_scope_refs_requires_source_package(tmp_path: Path):
    """Design start requires a committed source package."""
    import importlib.util

    adapter = TechDesignStartAdapter()
    with pytest.raises(ValueError, match="committed source-package"):
        adapter.resolve_scope_refs(
            delivered_refs=[DeliveredRef(type="lulu-approach", path="/abs/decision.md")],
            run_mode="tech",
        )

    approach = tmp_path / "approach"
    fact = _unit_fact(tmp_path)
    (approach / "main").mkdir(parents=True)
    main_fact = approach / "main" / "decision-fact.json"
    main_fact.write_text(fact.read_text(encoding="utf-8"), encoding="utf-8")
    (approach / "main" / "decision-doc.md").write_text("# main\n", encoding="utf-8")
    dp_path = (
        _WORKFLOW_ROOT
        / "lulu-approach"
        / "scripts"
        / "schema"
        / "decision_package_schema.py"
    )
    spec = importlib.util.spec_from_file_location("_dp_schema_scope_test", dp_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.save_decision_package(
        approach,
        mod.build_decision_package(
            main={
                "decision_fact_path": "main/decision-fact.json",
                "decision_doc_path": "main/decision-doc.md",
            },
            slices=[],
        ),
    )
    source_package = _write_approach_source_package(approach)
    rev = tmp_path / "design" / "revision1"
    rev.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str(source_package.resolve()),
                artifact="source-package",
            ),
        ],
        run_mode="tech",
        revision_dir=rev,
    )
    assert len(refs) == 1
    assert refs[0].artifact == "scope-package"
    assert Path(refs[0].path).name == "scope-package.json"


def _write_bet_source_package(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    fact = _unit_fact(root)
    return save_source_package(
        root,
        build_source_package(
            holder_stage="lulu-bet",
            commit_status="committed",
            slices=[
                {
                    "id": "L1",
                    "title": "main",
                    "source_path": fact.name,
                    "source_id": "main",
                }
            ],
        ),
    )


def test_product_spec_projects_bet_source_package(tmp_path: Path):
    adapter = ProductSpecStartAdapter()
    source = _write_bet_source_package(tmp_path / "bet")
    revision = tmp_path / "spec" / "revision1"
    revision.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-bet",
                path=str(source),
                artifact="source-package",
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
                "path": "/abs/source-package.json",
                "decision_fact_path": "/abs/decision-fact.json",
                "artifact": "source-package",
            }
        }
    }
    ref = ref_from_file_entry("lulu-bet", data)
    assert ref is not None
    assert ref.path == "/abs/source-package.json"
    assert ref.artifact == "source-package"
    assert "decision_fact_path" not in ref.to_dict()
    assert not hasattr(ref, "decision_fact_path")


def test_tech_arch_projects_approach_source_package(tmp_path: Path):
    adapter = TechArchStartAdapter()
    source_root = tmp_path / "approach"
    source_root.mkdir()
    fact = _unit_fact(source_root)
    source = save_source_package(
        source_root,
        build_source_package(
            holder_stage="lulu-approach",
            commit_status="committed",
            slices=[
                {
                    "id": "L1",
                    "title": "main",
                    "source_path": fact.name,
                    "source_id": "main",
                }
            ],
        ),
    )
    revision = tmp_path / "arch" / "revision1"
    revision.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str(source),
                artifact="source-package",
            ),
        ],
        revision_dir=revision,
    )
    assert refs[0].artifact == "scope-package"
    assert Path(refs[0].path) == revision / "scope-package.json"


def test_product_blueprint_projects_bet_source_package(tmp_path: Path):
    adapter = ProductBlueprintStartAdapter()
    source = _write_bet_source_package(tmp_path / "bet")
    revision = tmp_path / "blueprint" / "revision1"
    revision.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-bet",
                path=str(source),
                artifact="source-package",
            ),
        ],
        revision_dir=revision,
    )
    assert refs[0].artifact == "scope-package"
    assert Path(refs[0].path) == revision / "scope-package.json"


def test_tech_plan_approach_fallback_projects_source_package(tmp_path: Path):
    import importlib.util

    adapter = TechPlanStartAdapter()
    fact = _unit_fact(tmp_path)

    approach = tmp_path / "approach"
    (approach / "main").mkdir(parents=True)
    (approach / "main" / "decision-fact.json").write_text(
        fact.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (approach / "main" / "decision-doc.md").write_text("# main\n", encoding="utf-8")
    dp_path = (
        _WORKFLOW_ROOT
        / "lulu-approach"
        / "scripts"
        / "schema"
        / "decision_package_schema.py"
    )
    spec = importlib.util.spec_from_file_location("_dp_schema_plan_fallback", dp_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.save_decision_package(
        approach,
        mod.build_decision_package(
            main={
                "decision_fact_path": "main/decision-fact.json",
                "decision_doc_path": "main/decision-doc.md",
            },
            slices=[],
        ),
    )
    source_package = _write_approach_source_package(approach)
    rev = tmp_path / "plan" / "revision1"
    rev.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str(source_package.resolve()),
                artifact="source-package",
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
    import importlib.util

    adapter = TechDesignStartAdapter()
    fact = _unit_fact(tmp_path)
    approach = tmp_path / "approach"
    (approach / "main").mkdir(parents=True)
    (approach / "main" / "decision-fact.json").write_text(
        fact.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (approach / "main" / "decision-doc.md").write_text("# main\n", encoding="utf-8")
    dp_path = (
        _WORKFLOW_ROOT
        / "lulu-approach"
        / "scripts"
        / "schema"
        / "decision_package_schema.py"
    )
    spec = importlib.util.spec_from_file_location("_dp_scope_excl_spec", dp_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.save_decision_package(
        approach,
        mod.build_decision_package(
            main={
                "decision_fact_path": "main/decision-fact.json",
                "decision_doc_path": "main/decision-doc.md",
            },
            slices=[],
        ),
    )
    source_package = _write_approach_source_package(approach)
    rev = tmp_path / "design" / "revision1"
    rev.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str(source_package.resolve()),
                artifact="source-package",
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
