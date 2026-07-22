#!/usr/bin/env python3
"""Tests for display_layer_gates.py (fact-first display layer, M2, not wired)."""

from __future__ import annotations

import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent.parent / "section"
sys.path.insert(0, str(_SECTION))

from display_layer_gates import (  # noqa: E402
    check_c1,
    check_l1,
    check_l3,
    check_l4,
    check_q1,
    run_display_layer_gates,
)


def _fact(fid, tags):
    return {"id": fid, "text": f"text for {fid}", "lens_tags": tags}


def _chapter(cid, anchors, facts, *, op="keep"):
    return {
        "id": cid,
        "anchor_lenses": anchors,
        "op": op,
        "facts": facts,
    }


def _ref(fid, form_lens):
    return {"fid": fid, "form_lens": form_lens}


# ---- L1 --------------------------------------------------------------


def test_l1_accepts_exactly_once_placement():
    facts = [_fact("F-1", ["AR"]), _fact("F-2", ["AR"])]
    chapters = [_chapter("chap-1", ["AR"], [_ref("F-1", "AR"), _ref("F-2", "AR")])]
    assert check_l1(facts, chapters) == []


def test_l1_rejects_unassigned_should_render_fact():
    facts = [_fact("F-1", ["AR"]), _fact("F-2", ["AR"])]
    chapters = [_chapter("chap-1", ["AR"], [_ref("F-1", "AR")])]
    errors = check_l1(facts, chapters)
    assert any("F-2" in e and "unassigned" in e for e in errors)


def test_l1_rejects_duplicate_placement_across_chapters():
    facts = [_fact("F-1", ["AR"])]
    chapters = [
        _chapter("chap-1", ["AR"], [_ref("F-1", "AR")]),
        _chapter("chap-2", ["AR"], [_ref("F-1", "AR")]),
    ]
    errors = check_l1(facts, chapters)
    assert any("F-1" in e and "assigned 2 times" in e for e in errors)


def test_l1_rejects_duplicate_placement_within_one_chapter():
    facts = [_fact("F-1", ["AR"])]
    chapters = [_chapter("chap-1", ["AR"], [_ref("F-1", "AR"), _ref("F-1", "AR")])]
    errors = check_l1(facts, chapters)
    assert any("F-1" in e and "assigned 2 times" in e for e in errors)


def test_l1_rejects_quarantined_fact_placed_anywhere():
    facts = [_fact("F-1", [])]
    chapters = [_chapter("chap-1", ["AR"], [_ref("F-1", "AR")])]
    errors = check_l1(facts, chapters)
    assert any("quarantined" in e for e in errors)


def test_l1_rejects_quarantined_fact_hidden_in_drop_chapter():
    """Grok review Major#1: a quarantined fact must not hide in a drop chapter
    (drop chapters should be empty, but this gate does not
    trust that structural invariant blindly)."""
    facts = [_fact("F-1", [])]
    dropped = _chapter("chap-x", ["AR"], [_ref("F-1", "AR")], op="drop")
    errors = check_l1(facts, [dropped])
    assert any("quarantined" in e and "chap-x" in e for e in errors)


def test_l1_ignores_drop_chapters_for_assignment_count_and_flags_unknown_fid():
    facts = [_fact("F-1", ["AR"])]
    dropped = _chapter("chap-x", ["AR"], [], op="drop")
    live = _chapter("chap-1", ["AR"], [_ref("F-1", "AR"), _ref("F-99", "AR")])
    errors = check_l1(facts, [dropped, live])
    # F-1 is properly placed once -> no complaint about it.
    assert not any("F-1" in e for e in errors)
    # F-99 is not a known fact id -> flagged, not silently ignored.
    assert any("F-99" in e and "unknown fact id" in e for e in errors)


# ---- L3 --------------------------------------------------------------


def test_l3_accepts_legal_placement():
    facts = [_fact("F-1", ["AR", "SC"])]
    chapters = [_chapter("chap-1", ["AR"], [_ref("F-1", "AR")])]
    assert check_l3(facts, chapters) == []


def test_l3_rejects_no_intersection_with_declared_anchor():
    facts = [_fact("F-1", ["SC"])]
    chapters = [_chapter("chap-1", ["AR"], [_ref("F-1", "SC")])]
    errors = check_l3(facts, chapters)
    assert any("do not intersect" in e for e in errors)


def test_l3_rejects_form_lens_outside_own_lens_tags():
    # F-1 only claims SC; chapter anchors AR+SC so L3 intersection passes, but
    # form_lens=AR was never among F-1's own lens_tags -> cross-file half fails.
    facts = [_fact("F-1", ["SC"])]
    chapters = [_chapter("chap-1", ["AR", "SC"], [_ref("F-1", "AR")])]
    errors = check_l3(facts, chapters)
    assert any("not in its own" in e for e in errors)


def test_l3_skips_drop_chapters():
    facts = [_fact("F-1", ["SC"])]
    chapters = [_chapter("chap-1", ["AR"], [], op="drop")]
    assert check_l3(facts, chapters) == []


def test_l3_does_not_re_report_unknown_fid_already_covered_by_l1():
    """L3 skips fact refs whose fid is absent from _facts.json — L1 owns that error."""
    facts: list[dict] = []
    chapters = [_chapter("chap-1", ["AR"], [_ref("F-404", "AR")])]
    assert check_l3(facts, chapters) == []


# ---- L4 --------------------------------------------------------------


def test_l4_rejects_empty_rendered_chapter():
    chapters = [_chapter("chap-1", ["AR"], [])]
    errors = check_l4(chapters)
    assert any("empty chapter" in e for e in errors)


def test_l4_accepts_empty_drop_chapter_rejects_nonempty_drop():
    ok = [_chapter("chap-1", ["AR"], [], op="drop")]
    assert check_l4(ok) == []
    bad = [_chapter("chap-1", ["AR"], [_ref("F-1", "AR")], op="drop")]
    errors = check_l4(bad)
    assert any("dropped chapter" in e for e in errors)


# ---- C1 --------------------------------------------------------------


def test_c1_skipped_when_section_order_unknown():
    facts = [_fact("F-1", ["AR"])]
    assert check_c1(facts, section_order=None) == []


def test_c1_defaults_missing_presence_to_required():
    facts = [_fact("F-1", ["AR"])]
    errors = check_c1(facts, section_order=["AR", "SC"])
    assert any("SC" in e and "coverage gap" in e for e in errors)
    assert not any("'AR'" in e for e in errors)


def test_c1_allows_optional_lens_with_zero_facts():
    facts = [_fact("F-1", ["AR"])]
    errors = check_c1(
        facts,
        presence_map={"SC": "optional"},
        section_order=["AR", "SC"],
    )
    assert errors == []


def test_c1_accepts_lowercase_presence_map_keys():
    facts = [_fact("F-1", ["AR"])]
    errors = check_c1(
        facts,
        presence_map={"sc": "optional"},
        section_order=["AR", "SC"],
    )
    assert errors == []


def test_c1_treats_invalid_presence_value_as_required():
    facts = [_fact("F-1", ["AR"])]
    errors = check_c1(
        facts,
        presence_map={"SC": "sometimes"},
        section_order=["AR", "SC"],
    )
    assert any("SC" in e and "coverage gap" in e for e in errors)


def test_c1_with_dependency_graph_distinguishes_derivation_vs_true_gap():
    from derive_shell import normalize_dependency_graph

    facts = [_fact("F-1", ["AR"])]
    graph = normalize_dependency_graph(
        {
            "sections": {
                "AR": {"upstream": [], "relations": {}},
                "T": {
                    "upstream": ["AR"],
                    "relations": {"AR": "decompose"},
                },
                "ZZ": {"upstream": [], "relations": {}},
            },
        },
    )
    errors = check_c1(
        facts,
        presence_map={"AR": "required", "T": "required", "ZZ": "required"},
        section_order=["AR", "T", "ZZ"],
        dependency_graph=graph,
    )
    assert any("T" in e and "derivation lens" in e and "Step 2→3" in e for e in errors)
    assert any("ZZ" in e and "true gap" in e and "Round" in e for e in errors)
    assert not any("'AR'" in e for e in errors)


# ---- Q1 --------------------------------------------------------------


def test_q1_is_audit_only_never_blocks():
    facts = [_fact("F-1", ["AR"]), _fact("F-2", [])]
    audit = check_q1(facts)
    assert audit == {"quarantined_ids": ["F-2"], "quarantined_total": 1}


# ---- aggregator --------------------------------------------------------


def test_run_display_layer_gates_aggregates_errors_and_audit():
    facts = [_fact("F-1", ["AR"]), _fact("F-2", [])]
    chapters = [_chapter("chap-1", ["AR"], [_ref("F-1", "AR")])]
    result = run_display_layer_gates(
        facts,
        chapters,
        section_order=["AR"],
    )
    assert result["errors"] == []
    assert result["q1_audit"]["quarantined_total"] == 1


def test_run_display_layer_gates_reports_all_gate_violations_together():
    # F-1 tagged SC but chapter anchors AR -> L3 violation.
    # AR has zero tagging facts -> C1 coverage gap.
    facts = [_fact("F-1", ["SC"])]
    chapters = [_chapter("chap-1", ["AR"], [_ref("F-1", "SC")])]
    result = run_display_layer_gates(
        facts,
        chapters,
        section_order=["AR", "SC"],
    )
    joined = "; ".join(result["errors"])
    assert "L3" in joined
    assert "C1" in joined and "'AR'" in joined
