#!/usr/bin/env python3
"""Tests for TechPlanStartAdapter — resolve_delivered_refs + resolve_scope_facts_ref."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _SCRIPTS_ROOT.parents[1]
_KERNEL_TESTS = _WORKFLOW_ROOT / "compose" / "scripts" / "tests"
_START = _SCRIPTS_ROOT / "start"
for _p in (_KERNEL_TESTS, _START):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import bootstrap  # noqa: F401
from delivered_refs_schema import record_delivered_ref  # noqa: E402
from tech_plan_start_adapter import TechPlanStartAdapter  # noqa: E402

_CYCLE = "feat-plan-start"
_ADAPTER = TechPlanStartAdapter()


def _write_file(tmp_path: Path, rel: str, content: str = "# stub\n") -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _seed_design_ref(tmp_path: Path, cycle_id: str) -> Path:
    doc = _write_file(tmp_path, "design/design-doc.md")
    record_delivered_ref(
        cycle_id,
        tmp_path,
        delivered_type="lulu-design",
        path=str(doc.resolve()),
        revision=1,
        profile_id="lulu-design",
        source_workflow_state=str(doc.resolve()),
    )
    return doc


def _seed_design_facts_ref(tmp_path: Path, cycle_id: str) -> Path:
    facts = _write_file(tmp_path, "design/_facts.json", "[]\n")
    record_delivered_ref(
        cycle_id,
        tmp_path,
        delivered_type="lulu-design-facts",
        path=str(facts.resolve()),
        revision=1,
        profile_id="lulu-design",
        source_workflow_state=str(facts.resolve()),
    )
    return facts


def _seed_spec_ref(tmp_path: Path, cycle_id: str) -> Path:
    doc = _write_file(tmp_path, "spec/product-doc.md")
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


class TestResolveDeliveredRefs:
    def test_tech_mode_includes_design_facts_when_present(self, tmp_path: Path):
        _seed_design_ref(tmp_path, _CYCLE)
        facts = _seed_design_facts_ref(tmp_path, _CYCLE)
        refs = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        types = [r.type for r in refs]
        assert "lulu-design" in types
        assert "lulu-design-facts" in types
        assert any(r.path == str(facts.resolve()) for r in refs)

    def test_product_mode_includes_design_facts_when_present(self, tmp_path: Path):
        _seed_spec_ref(tmp_path, _CYCLE)
        _seed_design_ref(tmp_path, _CYCLE)
        _seed_design_facts_ref(tmp_path, _CYCLE)
        refs = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="product")
        types = [r.type for r in refs]
        assert "lulu-spec" in types
        assert "lulu-design" in types
        assert "lulu-design-facts" in types

    def test_tech_mode_omits_facts_when_absent(self, tmp_path: Path):
        _seed_design_ref(tmp_path, _CYCLE)
        refs = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        assert [r.type for r in refs] == ["lulu-design"]


class TestResolveScopeFactsRef:
    def test_returns_facts_ref_derived_from_scope_type(self, tmp_path: Path):
        _seed_design_ref(tmp_path, _CYCLE)
        facts = _seed_design_facts_ref(tmp_path, _CYCLE)
        delivered = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        out = _ADAPTER.resolve_scope_facts_ref(delivered_refs=delivered)
        assert len(out) == 1
        assert out[0].type == f"{delivered[0].type}-facts"
        assert out[0].path == str(facts.resolve())

    def test_approach_scope_has_no_facts_ref(self, tmp_path: Path):
        decision = _write_file(tmp_path, "approach/decision-doc.md")
        record_delivered_ref(
            _CYCLE,
            tmp_path,
            delivered_type="lulu-approach",
            path=str(decision.resolve()),
            revision=1,
            profile_id="lulu-approach",
            source_workflow_state=str(decision.resolve()),
        )
        delivered = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        assert [r.type for r in delivered] == ["lulu-approach"]
        assert _ADAPTER.resolve_scope_facts_ref(delivered_refs=delivered) == []


class TestStartWiringFactsRef:
    def test_getattr_write_resolved_refs_round_trip(self, tmp_path: Path):
        """Mirror start.py: optional resolve_scope_facts_ref → write_resolved_refs."""
        from resolved_refs_schema import (  # noqa: WPS433
            resolved_facts_ref,
            write_resolved_refs,
        )

        design = _seed_design_ref(tmp_path, _CYCLE)
        facts = _seed_design_facts_ref(tmp_path, _CYCLE)
        delivered = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        resolve_facts = getattr(_ADAPTER, "resolve_scope_facts_ref", None)
        assert resolve_facts is not None
        facts_refs = resolve_facts(delivered_refs=delivered)
        revision_dir = tmp_path / "revision1"
        revision_dir.mkdir()
        write_resolved_refs(
            revision_dir,
            cycle_id=_CYCLE,
            stage="lulu-plan",
            run_mode="tech",
            scope_ref=delivered[0],
            intent_baseline_refs=[],
            norm_constraint_refs=[],
            facts_ref=facts_refs[0] if facts_refs else None,
        )
        loaded = resolved_facts_ref(revision_dir)
        assert loaded is not None
        assert loaded.type == "lulu-design-facts"
        assert loaded.path == str(facts.resolve())
        del design
