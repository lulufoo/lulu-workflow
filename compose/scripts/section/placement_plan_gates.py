#!/usr/bin/env python3
"""Step 6 gates against archive-3.0 placement SoT (D2).

Reads in-memory ``_chapter-placement`` + themes + framework (no ``_chapters.json``).
Legacy chapter-array gates remain in ``display_layer_gates.py``.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from facts_schema import lenses_present, unlensed_fact_ids


def _facts_by_id(facts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {f["id"]: f for f in facts}


def themes_lens_key_map(themes: dict[str, Any]) -> dict[str, str]:
    return {
        e["form_lens_id"]: e["lens_key"]
        for e in themes.get("lens_themes") or []
    }


def framework_fl_by_chapter(framework: dict[str, Any]) -> dict[str, set[str]]:
    return {
        c["id"]: set(c.get("anchor_form_lens_ids") or [])
        for c in framework.get("chapters") or []
    }


def placement_chapters_as_l6_view(
    placement: dict[str, Any],
) -> list[dict[str, Any]]:
    """Minimal chapter view for L6 / artifact iteration (id + facts[].fid)."""
    return [
        {
            "id": c["id"],
            "op": "keep",
            "facts": [{"fid": f["fid"]} for f in c.get("facts") or []],
        }
        for c in placement.get("chapters") or []
    ]


def check_l1_placement(
    facts: list[dict[str, Any]],
    placement: dict[str, Any],
) -> list[str]:
    """Every should-render fact appears in exactly one placement chapter."""
    errors: list[str] = []
    facts_by_id = _facts_by_id(facts)
    should_render = {fid for fid, f in facts_by_id.items() if f.get("lens_tags")}
    quarantined = {fid for fid, f in facts_by_id.items() if not f.get("lens_tags")}

    assigned: Counter[str] = Counter()
    for chapter in placement.get("chapters") or []:
        cid = chapter.get("id")
        for fact_ref in chapter.get("facts") or []:
            fid = fact_ref.get("fid")
            if fid in quarantined:
                errors.append(
                    f"L1: quarantined fact {fid!r} (empty lens_tags) is assigned "
                    f"to chapter {cid!r}; quarantined facts must not be placed",
                )
            elif fid not in facts_by_id:
                errors.append(
                    f"L1: chapter {cid!r} references unknown fact id {fid!r} "
                    "(not in _facts.json)",
                )
            assigned[fid] += 1

    for fid in sorted(should_render):
        count = assigned.get(fid, 0)
        if count == 0:
            errors.append(
                f"L1: fact {fid!r} should render but is unassigned in "
                "_chapter-placement.json",
            )
        elif count > 1:
            errors.append(
                f"L1: fact {fid!r} assigned {count} times (must be exactly once)",
            )
    return errors


def check_l3_placement(
    facts: list[dict[str, Any]],
    placement: dict[str, Any],
    themes: dict[str, Any],
    framework: dict[str, Any],
) -> list[str]:
    """Legal placement: form_lens_id ∈ chapter anchors; lens_key ∈ fact.lens_tags."""
    errors: list[str] = []
    facts_by_id = _facts_by_id(facts)
    key_by_fl = themes_lens_key_map(themes)
    fl_by_cid = framework_fl_by_chapter(framework)

    for chapter in placement.get("chapters") or []:
        cid = chapter.get("id")
        allowed_fl = fl_by_cid.get(cid, set())
        for fact_ref in chapter.get("facts") or []:
            fid = fact_ref.get("fid")
            fact = facts_by_id.get(fid)
            if fact is None:
                continue
            fl = str(fact_ref.get("form_lens_id", "")).strip()
            if fl not in allowed_fl:
                errors.append(
                    f"L3: fact {fid!r} form_lens_id {fl!r} not in chapter "
                    f"{cid!r} anchor_form_lens_ids {sorted(allowed_fl)}",
                )
            lens_key = key_by_fl.get(fl)
            tags = set(fact.get("lens_tags") or [])
            if not lens_key:
                errors.append(
                    f"L3: fact {fid!r} form_lens_id {fl!r} has no lens_key in themes",
                )
            elif lens_key not in tags:
                errors.append(
                    f"L3: fact {fid!r} lens_key {lens_key!r} (via {fl}) not in "
                    f"its own lens_tags {sorted(tags)}",
                )
    return errors


def check_l4_placement(placement: dict[str, Any]) -> list[str]:
    """Every placement chapter must carry at least one fact."""
    errors: list[str] = []
    for chapter in placement.get("chapters") or []:
        cid = chapter.get("id")
        if not chapter.get("facts"):
            errors.append(
                f"L4: placement chapter {cid!r} has zero facts (empty chapter)",
            )
    return errors


def check_c1_facts(
    facts: list[dict[str, Any]],
    *,
    presence_map: dict[str, str] | None = None,
    section_order: list[str] | None = None,
    dependency_graph: dict[str, Any] | None = None,
) -> list[str]:
    """Reuse C1 semantics from display_layer_gates (facts-only)."""
    from display_layer_gates import check_c1

    return check_c1(
        facts,
        presence_map=presence_map,
        section_order=section_order,
        dependency_graph=dependency_graph,
    )


def run_placement_plan_gates(
    facts: list[dict[str, Any]],
    placement: dict[str, Any],
    themes: dict[str, Any],
    framework: dict[str, Any],
    *,
    presence_map: dict[str, str] | None = None,
    section_order: list[str] | None = None,
    dependency_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Blocking L1/L3/L4/C1 against placement SoT; Q1 advisory."""
    errors: list[str] = []
    errors.extend(check_l1_placement(facts, placement))
    errors.extend(check_l3_placement(facts, placement, themes, framework))
    errors.extend(check_l4_placement(placement))
    errors.extend(
        check_c1_facts(
            facts,
            presence_map=presence_map,
            section_order=section_order,
            dependency_graph=dependency_graph,
        ),
    )
    return {
        "errors": errors,
        "q1_audit": {
            "quarantined_ids": unlensed_fact_ids(facts),
            "quarantined_total": len(unlensed_fact_ids(facts)),
        },
        "coverage": lenses_present(facts),
    }
