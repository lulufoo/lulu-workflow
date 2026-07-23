#!/usr/bin/env python3
"""Tests for TechPlanStartAdapter — resolve_delivered_refs and start wiring."""

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


def _seed_design_with_legacy_facts_key(tmp_path: Path, cycle_id: str) -> Path:
    """Seed design entry plus a leftover on-disk facts_path (ignored by readers)."""
    doc = _write_file(tmp_path, "design/design-doc.md")
    facts = _write_file(tmp_path, "design/_facts.json", "[]\n")
    path = delivered_refs_file_path(cycle_id, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = (
        load_delivered_refs_file(cycle_id, tmp_path)
        if path.is_file()
        else {"version": 1, "entries": {}}
    )
    entries = dict(existing.get("entries") or {})
    entries["lulu-design"] = {
        "delivered_type": "lulu-design",
        "path": str(doc.resolve()),
        "revision": 1,
        "profile_id": "lulu-design",
        "delivered_at": "2026-01-01T00:00:00+00:00",
        "source_workflow_state": str(doc.resolve()),
        "facts_path": str(facts.resolve()),
    }
    existing["version"] = int(existing.get("version") or 1)
    existing["entries"] = entries
    save_delivered_refs_file(cycle_id, tmp_path, existing)
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
    def test_tech_mode_returns_design_doc_only(self, tmp_path: Path):
        _seed_design_with_legacy_facts_key(tmp_path, _CYCLE)
        refs = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        types = [r.type for r in refs]
        assert types == ["lulu-design"]
        assert not hasattr(refs[0], "facts_path")
        assert "lulu-design-facts" not in types

    def test_product_mode_includes_design_doc(self, tmp_path: Path):
        _seed_spec_ref(tmp_path, _CYCLE)
        _seed_design_with_legacy_facts_key(tmp_path, _CYCLE)
        refs = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="product")
        types = [r.type for r in refs]
        assert "lulu-spec" in types
        assert "lulu-design" in types
        assert "lulu-design-facts" not in types

    def test_tech_mode_design_without_legacy_key(self, tmp_path: Path):
        _seed_design_ref(tmp_path, _CYCLE)
        refs = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
        assert [r.type for r in refs] == ["lulu-design"]


class TestNoScopeFactsRef:
    def test_adapter_has_no_resolve_scope_facts_ref(self):
        assert not hasattr(_ADAPTER, "resolve_scope_facts_ref")

    def test_write_resolved_refs_omits_facts_ref(self, tmp_path: Path):
        from resolved_refs_schema import load_resolved_refs, write_resolved_refs

        _seed_design_with_legacy_facts_key(tmp_path, _CYCLE)
        delivered = _ADAPTER.resolve_delivered_refs(_CYCLE, tmp_path, run_mode="tech")
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
        )
        data = load_resolved_refs(revision_dir)
        assert "facts_ref" not in data


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
        )
        data = load_delivered_refs_file(_CYCLE, tmp_path)
        assert "lulu-design-facts" not in data["entries"]
        assert "facts_path" not in data["entries"]["lulu-design"]
