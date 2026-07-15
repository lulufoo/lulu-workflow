#!/usr/bin/env python3
"""Tests for derive_shell.py (kernel K1 mechanical shell, Step 3 — Derive facts)."""

from __future__ import annotations

import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent.parent / "section"
sys.path.insert(0, str(_SECTION))

from derive_shell import (  # noqa: E402
    DeriveCycleError,
    append_derived_facts,
    check_derive_nonempty_self_audit,
    classify_zero_required_lenses,
    derivation_upstreams,
    derive_triggers,
    has_derivation,
    normalize_dependency_graph,
    topo_order_triggered,
    true_coverage_gaps,
    upstream_fact_count,
)


def _graph(**sections: dict) -> dict:
    """Build dependency-graph subset from section entries.

    Each value: ``{"upstream": [...], "relations": {U: type}}``.
    """
    out: dict[str, dict] = {}
    for key, entry in sections.items():
        k = key.upper()
        upstream = [str(u).upper() for u in entry.get("upstream") or []]
        relations = {
            str(rk).upper(): str(rv)
            for rk, rv in (entry.get("relations") or {}).items()
        }
        out[k] = {"upstream": upstream, "relations": relations}
    return {"sections": out}


def _planish_graph():
    # AR ← (none); SK ← AR operationalize; T ← SK/AR decompose
    return _graph(
        AR={"upstream": [], "relations": {}},
        SK={"upstream": ["AR"], "relations": {"AR": "operationalize"}},
        T={
            "upstream": ["SK", "AR"],
            "relations": {"SK": "decompose", "AR": "instantiate"},
        },
        GO={"upstream": [], "relations": {}},
    )


def test_has_derivation_and_upstreams():
    g = _planish_graph()
    assert has_derivation("T", g) is True
    assert has_derivation("SK", g) is False  # operationalize only
    assert has_derivation("GO", g) is False
    assert derivation_upstreams("T", g) == ["SK", "AR"]


def test_derive_triggers_zero_only_required_with_edge():
    g = _planish_graph()
    order = ["AR", "SK", "T", "GO"]
    presence = {"AR": "required", "SK": "required", "T": "required", "GO": "optional"}
    facts = [
        {"id": "F-1", "text": "ar fact", "lens_tags": ["AR"]},
        {"id": "F-2", "text": "sk fact", "lens_tags": ["SK"]},
    ]
    assert derive_triggers(order, presence, facts, g) == ["T"]


def test_derive_triggers_skips_partial_coverage_zero_only():
    """required ∧ facts>0 ∧ derivation edge → do NOT trigger (zero-only)."""
    g = _planish_graph()
    order = ["T"]
    presence = {"T": "required"}
    facts = [{"id": "F-1", "text": "partial T", "lens_tags": ["T"]}]
    assert derive_triggers(order, presence, facts, g) == []


def test_derive_triggers_skips_optional_and_true_gaps():
    g = _planish_graph()
    order = ["T", "GO", "ZZ"]
    # ZZ required, zero facts, no derivation edge → true gap, not trigger
    g["sections"]["ZZ"] = {"upstream": [], "relations": {}}
    presence = {"T": "required", "GO": "optional", "ZZ": "required"}
    facts = [{"id": "F-1", "text": "sk", "lens_tags": ["SK"]}]
    assert derive_triggers(order, presence, facts, g) == ["T"]
    assert true_coverage_gaps(order, presence, facts, g) == ["ZZ"]


def test_topo_order_upstream_first_cascade():
    # Both SK and T trigger; SK derives from AR via decompose.
    g = _graph(
        AR={"upstream": [], "relations": {}},
        SK={"upstream": ["AR"], "relations": {"AR": "decompose"}},
        T={"upstream": ["SK"], "relations": {"SK": "decompose"}},
    )
    triggered = ["T", "SK"]  # deliberate reverse of topo
    assert topo_order_triggered(triggered, g) == ["SK", "T"]


def test_topo_order_raises_on_cycle():
    g = _graph(
        A={"upstream": ["B"], "relations": {"B": "decompose"}},
        B={"upstream": ["A"], "relations": {"A": "instantiate"}},
    )
    try:
        topo_order_triggered(["A", "B"], g)
        assert False, "expected DeriveCycleError"
    except DeriveCycleError as exc:
        assert "cycle" in str(exc).lower()


def test_append_derived_facts_contiguous_ids_and_source():
    base = [
        {"id": "F-1", "text": "sk", "lens_tags": ["SK"]},
        {"id": "F-2", "text": "ar", "lens_tags": ["AR"]},
    ]
    derived = [
        {
            "text": "task one",
            "lens_tags": ["T"],
            "source": ["F-1"],
        },
        {
            "text": "task two",
            "lens_tags": ["T"],
            "source": ["F-2", "按 AR 契约"],
        },
    ]
    out = append_derived_facts(base, derived)
    assert [f["id"] for f in out] == ["F-1", "F-2", "F-3", "F-4"]
    assert out[2]["lens_tags"] == ["T"]
    assert out[2]["source"] == ["F-1"]
    assert out[3]["source"] == ["F-2", "按 AR 契约"]


def test_cascade_visibility_via_append_then_filter():
    """Later lens sees earlier Step 3 appends (same-pass cascade)."""
    g = _graph(
        SK={"upstream": ["AR"], "relations": {"AR": "decompose"}},
        T={"upstream": ["SK"], "relations": {"SK": "decompose"}},
        AR={"upstream": [], "relations": {}},
    )
    facts = [{"id": "F-1", "text": "ar", "lens_tags": ["AR"]}]
    presence = {"SK": "required", "T": "required", "AR": "required"}
    assert derive_triggers(["AR", "SK", "T"], presence, facts, g) == ["SK", "T"]
    order = topo_order_triggered(["SK", "T"], g)
    assert order == ["SK", "T"]
    facts = append_derived_facts(
        facts,
        [{"text": "sk from ar", "lens_tags": ["SK"], "source": ["F-1"]}],
    )
    assert upstream_fact_count(facts, "T", g) == 1
    facts = append_derived_facts(
        facts,
        [{"text": "t from sk", "lens_tags": ["T"], "source": ["F-2"]}],
    )
    assert any(f["id"] == "F-3" and f["lens_tags"] == ["T"] for f in facts)


def test_self_audit_flags_empty_emit_when_upstream_nonempty():
    g = _planish_graph()
    before = [
        {"id": "F-1", "text": "sk", "lens_tags": ["SK"]},
        {"id": "F-2", "text": "ar", "lens_tags": ["AR"]},
    ]
    after = list(before)  # Step 3 emitted nothing for T
    errors = check_derive_nonempty_self_audit(before, after, ["T"], g)
    assert len(errors) == 1
    assert "T" in errors[0]


def test_self_audit_skips_empty_upstream():
    g = _planish_graph()
    before = [{"id": "F-1", "text": "go only", "lens_tags": ["GO"]}]
    after = list(before)
    assert check_derive_nonempty_self_audit(before, after, ["T"], g) == []


def test_self_audit_cascade_aware_uses_facts_after():
    """Major: SK derived mid-pass must count as upstream for T (facts_after).

    Before-only upstream counting would skip T (SK empty at Step 2) and miss the
    silent-T failure after SK was appended in the same Step 3 pass.
    """
    g = _graph(
        AR={"upstream": [], "relations": {}},
        SK={"upstream": ["AR"], "relations": {"AR": "decompose"}},
        T={"upstream": ["SK"], "relations": {"SK": "decompose"}},
    )
    before = [{"id": "F-1", "text": "ar", "lens_tags": ["AR"]}]
    # Same-pass: SK derived, T stayed silent
    after = [
        {"id": "F-1", "text": "ar", "lens_tags": ["AR"]},
        {
            "id": "F-2",
            "text": "sk from ar",
            "lens_tags": ["SK"],
            "source": ["F-1"],
        },
    ]
    errors = check_derive_nonempty_self_audit(before, after, ["SK", "T"], g)
    assert len(errors) == 1
    assert "T" in errors[0]
    # SK itself gained a new fact → no error for SK
    assert not any("SK" in e and "T" not in e for e in errors)


def test_self_audit_accepts_daijue_as_emit():
    """待决 facts still count as real emits for the triggered lens."""
    g = _planish_graph()
    before = [
        {"id": "F-1", "text": "sk", "lens_tags": ["SK"]},
        {"id": "F-2", "text": "ar", "lens_tags": ["AR"]},
    ]
    after = before + [
        {
            "id": "F-3",
            "text": "待决：任务边界是否含回滚脚本",
            "lens_tags": ["T"],
            "source": ["F-1"],
        },
    ]
    assert check_derive_nonempty_self_audit(before, after, ["T"], g) == []


def test_classify_zero_required_lenses_buckets():
    g = _planish_graph()
    g["sections"]["ZZ"] = {"upstream": [], "relations": {}}
    order = ["AR", "SK", "T", "GO", "ZZ"]
    presence = {
        "AR": "required",
        "SK": "required",
        "T": "required",
        "GO": "optional",
        "ZZ": "required",
    }
    facts = [
        {"id": "F-1", "text": "ar", "lens_tags": ["AR"]},
        {"id": "F-2", "text": "sk", "lens_tags": ["SK"]},
    ]
    buckets = classify_zero_required_lenses(order, presence, facts, g)
    assert buckets["derivation"] == ["T"]
    assert buckets["true_gaps"] == ["ZZ"]


def test_normalize_dependency_graph_lowercases_relations():
    raw = {
        "sections": {
            "t": {
                "upstream": ["sk"],
                "relations": {"sk": "Decompose"},
            },
        },
    }
    g = normalize_dependency_graph(raw)
    assert g["sections"]["T"]["relations"]["SK"] == "decompose"
    assert has_derivation("T", g) is True


def test_planish_e2e_append_c1_pass_with_source():
    """§7.3 mechanical e2e: Step 2 T=0 → Step 3 append → C1 pass + source preserved."""
    from display_layer_gates import check_c1

    g = _planish_graph()
    order = ["AR", "SK", "T", "GO"]
    presence = {"AR": "required", "SK": "required", "T": "required", "GO": "optional"}
    step2_facts = [
        {"id": "F-1", "text": "ar contract", "lens_tags": ["AR"]},
        {"id": "F-2", "text": "sk phase", "lens_tags": ["SK"]},
    ]
    assert derive_triggers(order, presence, step2_facts, g) == ["T"]
    assert true_coverage_gaps(order, presence, step2_facts, g) == []
    c1_before = check_c1(
        step2_facts,
        presence_map=presence,
        section_order=order,
        dependency_graph=g,
    )
    assert any("T" in e and "derivation lens" in e for e in c1_before)
    after = append_derived_facts(
        step2_facts,
        [
            {
                "text": "implement phase gate",
                "lens_tags": ["T"],
                "source": ["F-2", "按 AR 契约"],
            },
        ],
    )
    assert after[-1]["id"] == "F-3"
    assert after[-1]["source"] == ["F-2", "按 AR 契约"]
    assert check_derive_nonempty_self_audit(step2_facts, after, ["T"], g) == []
    assert (
        check_c1(
            after,
            presence_map=presence,
            section_order=order,
            dependency_graph=g,
        )
        == []
    )
