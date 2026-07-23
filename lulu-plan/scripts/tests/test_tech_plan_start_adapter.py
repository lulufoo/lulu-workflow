#!/usr/bin/env python3
"""Tests for TechPlanStartAdapter — resolve_delivered_refs + resolve_scope_facts_ref."""

from __future__ import annotations

import json
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
from cycle_delivered_refs import (  # noqa: E402
    delivered_refs_file_path,
    load_delivered_refs_file,
    record_delivered_ref,
    save_delivered_refs_file,
)
from tech_plan_start_adapter import TechPlanStartAdapter  # noqa: E402

_CYCLE = "feat-plan-start"
_ADAPTER = TechPlanStartAdapter()


def _write_file(tmp_path: Path, rel: str, content: str = "# stub\n") -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return p


def _seed_design_ref(
    tmp_path: Path,
    cycle_id: str,
    *,
    facts_path: str | None = None,
) -> Path:
    doc = _write_file(tmp_path, "design/design-doc.md")
    record_delivered_ref(
        cycle_id,
        tmp_path,
        delivered_type="lulu-design",
        path=str(doc.resolve()),
        revision=1,
        profile_id="lulu-design",
        source_workflow_state=str(doc.resolve()),
        facts_path=facts_path,
    )
    return doc


def _seed_design_with_facts(tmp_path: Path, cycle_id: str) -> Path:
    facts = _write_file(tmp_path, "design/_facts.json", "[]\n")
    _seed_design_ref(tmp_path, cycle_id, facts_path=str(facts.resolve()))
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
    def test_tech_mode_carries_facts_path_on_design_entry(self, tmp_path: Path):
        facts = _seed_design_with_facts(tmp_path, _CYCLE)
        refs = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        types = [r.type for r in refs]
        assert types == ["lulu-design"]
        assert refs[0].facts_path == str(facts.resolve())
        assert "lulu-design-facts" not in types

    def test_product_mode_includes_design_with_facts_path(self, tmp_path: Path):
        _seed_spec_ref(tmp_path, _CYCLE)
        facts = _seed_design_with_facts(tmp_path, _CYCLE)
        refs = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="product")
        types = [r.type for r in refs]
        assert "lulu-spec" in types
        assert "lulu-design" in types
        assert "lulu-design-facts" not in types
        design = next(r for r in refs if r.type == "lulu-design")
        assert design.facts_path == str(facts.resolve())

    def test_tech_mode_omits_facts_when_absent(self, tmp_path: Path):
        _seed_design_ref(tmp_path, _CYCLE)
        refs = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        assert [r.type for r in refs] == ["lulu-design"]
        assert refs[0].facts_path == ""


class TestResolveScopeFactsRef:
    def test_ignores_stage_facts_path(self, tmp_path: Path):
        """U17: delivery SSOT=doc — never surface upstream facts_path."""
        _seed_design_with_facts(tmp_path, _CYCLE)
        delivered = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        assert _ADAPTER.resolve_scope_facts_ref(delivered_refs=delivered) == []

    def test_ignores_legacy_parallel_facts_key(self, tmp_path: Path):
        doc = _write_file(tmp_path, "design/design-doc.md")
        facts = _write_file(tmp_path, "design/_facts.json", "[]\n")
        path = delivered_refs_file_path(_CYCLE, tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "entries": {
                "lulu-design": {
                    "delivered_type": "lulu-design",
                    "path": str(doc.resolve()),
                    "revision": 1,
                    "profile_id": "lulu-design",
                    "delivered_at": "2026-01-01T00:00:00+00:00",
                    "source_workflow_state": str(doc.resolve()),
                },
                "lulu-design-facts": {
                    "delivered_type": "lulu-design-facts",
                    "path": str(facts.resolve()),
                    "revision": 1,
                    "profile_id": "lulu-design",
                    "delivered_at": "2026-01-01T00:00:00+00:00",
                    "source_workflow_state": str(facts.resolve()),
                },
            },
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        delivered = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        assert _ADAPTER.resolve_scope_facts_ref(delivered_refs=delivered) == []

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
    def test_getattr_write_resolved_refs_empty_facts(self, tmp_path: Path):
        """Mirror start.py: resolve_scope_facts_ref is always empty (U17)."""
        from resolved_refs_schema import (  # noqa: WPS433
            resolved_facts_ref,
            write_resolved_refs,
        )

        _seed_design_with_facts(tmp_path, _CYCLE)
        delivered = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        resolve_facts = getattr(_ADAPTER, "resolve_scope_facts_ref", None)
        assert resolve_facts is not None
        assert resolve_facts(delivered_refs=delivered) == []
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
            facts_ref=None,
        )
        assert resolved_facts_ref(revision_dir) is None


class TestRecordDropsLegacyFactsKey:
    def test_upsert_removes_parallel_facts_key(self, tmp_path: Path):
        doc = _write_file(tmp_path, "design/design-doc.md")
        facts = _write_file(tmp_path, "design/_facts.json", "[]\n")
        path = delivered_refs_file_path(_CYCLE, tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        save_delivered_refs_file(
            _CYCLE,
            tmp_path,
            {
                "version": 1,
                "entries": {
                    "lulu-design-facts": {
                        "delivered_type": "lulu-design-facts",
                        "path": str(facts.resolve()),
                        "revision": 1,
                        "profile_id": "lulu-design",
                        "delivered_at": "2026-01-01T00:00:00+00:00",
                        "source_workflow_state": str(facts.resolve()),
                    },
                },
            },
        )
        record_delivered_ref(
            _CYCLE,
            tmp_path,
            delivered_type="lulu-design",
            path=str(doc.resolve()),
            revision=1,
            profile_id="lulu-design",
            source_workflow_state=str(doc.resolve()),
            facts_path=str(facts.resolve()),
        )
        data = load_delivered_refs_file(_CYCLE, tmp_path)
        assert "lulu-design-facts" not in data["entries"]
        assert data["entries"]["lulu-design"]["facts_path"] == str(facts.resolve())
