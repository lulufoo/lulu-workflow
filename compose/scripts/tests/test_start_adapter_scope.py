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
):
    _p = _WORKFLOW_ROOT / _rel
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bootstrap  # noqa: F401
from delivered_refs_schema import DeliveredRef  # noqa: E402
from product_blueprint_start_adapter import ProductBlueprintStartAdapter  # noqa: E402
from product_spec_start_adapter import ProductSpecStartAdapter  # noqa: E402
from start_scope_helpers import (  # noqa: E402
    DecisionFactScopeError,
    require_decision_fact_scope,
)
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


def test_tech_plan_resolve_scope_refs_primary_tech_chain():
    adapter = TechPlanStartAdapter()
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(type="lulu-approach", path="/abs/decision.md"),
            DeliveredRef(type="lulu-design", path="/abs/design.md"),
        ],
        run_mode="tech",
    )
    assert len(refs) == 1
    assert refs[0].type == "lulu-design"


def test_tech_plan_approach_only_requires_decision_fact(tmp_path: Path):
    adapter = TechPlanStartAdapter()
    with pytest.raises(DecisionFactScopeError, match="required"):
        adapter.resolve_scope_refs(
            delivered_refs=[
                DeliveredRef(type="lulu-approach", path="/abs/decision.md"),
                DeliveredRef(type="lulu-spec", path="/abs/product.md"),
            ],
            run_mode="product",
        )
    fact = _unit_fact(tmp_path)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path="/abs/decision.md",
                decision_fact_path=str(fact.resolve()),
            ),
            DeliveredRef(type="lulu-spec", path="/abs/product.md"),
        ],
        run_mode="product",
    )
    assert refs[0].type == "lulu-approach"
    assert refs[0].path == str(fact.resolve())


def test_tech_design_resolve_scope_refs_requires_decision_package(tmp_path: Path):
    """Archive-1.0: design start retires legacy whole decision-fact Path A."""
    import importlib.util

    adapter = TechDesignStartAdapter()
    with pytest.raises(ValueError, match="decision-package|Path A|retired"):
        adapter.resolve_scope_refs(
            delivered_refs=[DeliveredRef(type="lulu-approach", path="/abs/decision.md")],
            run_mode="tech",
        )
    fact = _unit_fact(tmp_path)
    with pytest.raises(ValueError, match="decision-package|Path A|retired"):
        adapter.resolve_scope_refs(
            delivered_refs=[
                DeliveredRef(
                    type="lulu-approach",
                    path="/abs/decision.md",
                    decision_fact_path=str(fact.resolve()),
                ),
            ],
            run_mode="tech",
        )

    approach = tmp_path / "approach"
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
    rev = tmp_path / "design" / "revision1"
    rev.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str((approach / "decision-package.json").resolve()),
                artifact="decision-package",
            ),
        ],
        run_mode="tech",
        revision_dir=rev,
    )
    assert len(refs) == 1
    assert refs[0].artifact == "scope-package"
    assert Path(refs[0].path).name == "scope-package.json"


def test_tech_design_resolve_scope_refs_legacy_fact_hard_fail(tmp_path: Path):
    adapter = TechDesignStartAdapter()
    fact = _unit_fact(tmp_path)
    with pytest.raises(ValueError, match="decision-package|Path A|retired"):
        adapter.resolve_scope_refs(
            delivered_refs=[
                DeliveredRef(
                    type="lulu-approach",
                    path="/abs/decision.md",
                    decision_fact_path=str(fact.resolve()),
                ),
            ],
            run_mode="tech",
        )

    empty = tmp_path / "empty-fact.json"
    empty.write_text('{"version":1,"gates":{}}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="decision-package|Path A|retired"):
        adapter.resolve_scope_refs(
            delivered_refs=[
                DeliveredRef(
                    type="lulu-approach",
                    path="/abs/decision.md",
                    decision_fact_path=str(empty.resolve()),
                ),
            ],
        )

    missing = tmp_path / "missing.json"
    with pytest.raises(ValueError, match="decision-package|Path A|retired"):
        adapter.resolve_scope_refs(
            delivered_refs=[
                DeliveredRef(
                    type="lulu-approach",
                    path="/abs/decision.md",
                    decision_fact_path=str(missing),
                ),
            ],
        )
    corrupt = tmp_path / "corrupt-fact.json"
    corrupt.write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match="decision-package|Path A|retired"):
        adapter.resolve_scope_refs(
            delivered_refs=[
                DeliveredRef(
                    type="lulu-approach",
                    path="/abs/decision.md",
                    decision_fact_path=str(corrupt.resolve()),
                ),
            ],
        )


def test_product_spec_resolve_scope_refs_requires_fact(tmp_path: Path):
    adapter = ProductSpecStartAdapter()
    with pytest.raises(DecisionFactScopeError, match="required"):
        adapter.resolve_scope_refs(
            delivered_refs=[DeliveredRef(type="lulu-bet", path="/abs/decision.md")],
            run_mode="product",
        )
    fact = _unit_fact(tmp_path)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-bet",
                path="/abs/decision.md",
                decision_fact_path=str(fact.resolve()),
            ),
        ],
        run_mode="product",
    )
    assert refs[0].type == "lulu-bet"
    assert refs[0].path == str(fact.resolve())


def test_require_decision_fact_scope_helper(tmp_path: Path):
    fact = _unit_fact(tmp_path)
    preferred = require_decision_fact_scope(
        DeliveredRef(
            type="lulu-bet",
            path="/abs/decision.md",
            decision_fact_path=str(fact.resolve()),
        )
    )
    assert preferred.path == str(fact.resolve())
    with pytest.raises(DecisionFactScopeError, match="required"):
        require_decision_fact_scope(
            DeliveredRef(type="lulu-bet", path="/abs/decision.md")
        )


def test_product_spec_requires_decision_fact(tmp_path: Path):
    adapter = ProductSpecStartAdapter()
    fact = _unit_fact(tmp_path)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-bet",
                path="/abs/bet.md",
                decision_fact_path=str(fact.resolve()),
            ),
        ],
    )
    assert refs[0].path == str(fact.resolve())


def test_tech_arch_requires_decision_fact(tmp_path: Path):
    adapter = TechArchStartAdapter()
    fact = _unit_fact(tmp_path)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path="/abs/decision.md",
                decision_fact_path=str(fact.resolve()),
            ),
        ],
    )
    assert refs[0].path == str(fact.resolve())


def test_product_blueprint_requires_decision_fact(tmp_path: Path):
    adapter = ProductBlueprintStartAdapter()
    fact = _unit_fact(tmp_path)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-bet",
                path="/abs/bet.md",
                decision_fact_path=str(fact.resolve()),
            ),
        ],
    )
    assert refs[0].path == str(fact.resolve())


def test_tech_plan_approach_fallback_requires_decision_fact(tmp_path: Path):
    adapter = TechPlanStartAdapter()
    fact = _unit_fact(tmp_path)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path="/abs/decision.md",
                decision_fact_path=str(fact.resolve()),
            ),
        ],
    )
    assert refs[0].type == "lulu-approach"
    assert refs[0].path == str(fact.resolve())


def test_tech_plan_design_primary_keeps_design_doc_path(tmp_path: Path):
    adapter = TechPlanStartAdapter()
    fact = _unit_fact(tmp_path)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path="/abs/decision.md",
                decision_fact_path=str(fact.resolve()),
            ),
            DeliveredRef(type="lulu-design", path="/abs/design.md"),
        ],
    )
    assert refs[0].type == "lulu-design"
    assert refs[0].path == "/abs/design.md"


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
    rev = tmp_path / "design" / "revision1"
    rev.mkdir(parents=True)
    refs = adapter.resolve_scope_refs(
        delivered_refs=[
            DeliveredRef(
                type="lulu-approach",
                path=str((approach / "decision-package.json").resolve()),
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
