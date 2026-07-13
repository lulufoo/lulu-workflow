#!/usr/bin/env python3
"""Step 6 placement gates for the fact-first display layer (increment 1, M2).

Design rationale (source repo, why-only): docs/biz/compose-fact-first-theory/compose-fact-first-display-layer-design.md §8.2, §11.2.

Pure functions only — no file I/O, no markdown parsing. Callers load
``_facts.json`` / ``_chapters.json`` via ``facts_schema.load_facts`` /
``chapters_schema.load_chapters`` and pass the normalized lists in.

Wired into ``init_compose_validation.validate_display_layer_artifacts`` (fact-first
Init Step 6). Module name keeps the historical ``display_layer_*`` prefix. That
caller also adds chapter-artifact-existence and assembly-completeness gates
outside this module — see design §11 M4a row and §11.2 "边界" note.

Gate coverage (design §8.2): L1, L3, L4, L5, C1, Q1.
L2 ("placement consistency") is **not** a function here — with a single
placement SoT (``_chapters.json``) it holds by construction. There is no
markdown projection-fidelity half: the design deliberately drops
proposition-level content-fidelity checking against the rendered document
(``.md`` is a one-way projection, never read back as SoT); M4a's structural
assembly-completeness check (anchor + non-empty body present) is the only
markdown-facing gate and lives in ``init_compose_validation.py``, not here.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from facts_schema import lenses_present, unlensed_fact_ids


def _facts_by_id(facts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {f["id"]: f for f in facts}


def check_l1(
    facts: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
) -> list[str]:
    """Every fact that should render appears in exactly one non-drop chapter;
    quarantined (empty ``lens_tags``) facts must not be assigned anywhere."""
    errors: list[str] = []
    facts_by_id = _facts_by_id(facts)
    should_render = {fid for fid, f in facts_by_id.items() if f.get("lens_tags")}
    quarantined = {fid for fid, f in facts_by_id.items() if not f.get("lens_tags")}

    assigned: Counter[str] = Counter()
    for chapter in chapters:
        is_drop = chapter.get("op") == "drop"
        cid = chapter.get("id")
        for fact_ref in chapter.get("facts", []):
            fid = fact_ref.get("fid")
            # Quarantine / unknown-id checks scan **all** chapters, including
            # `drop` — a dropped chapter is genealogy-only and (per
            # chapters_schema) should carry no facts at all, but this gate
            # does not trust that structural invariant blindly (Grok review
            # Major#1: a quarantined fact must not hide in a drop chapter).
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
            if not is_drop:
                assigned[fid] += 1

    for fid in sorted(should_render):
        count = assigned.get(fid, 0)
        if count == 0:
            errors.append(
                f"L1: fact {fid!r} should render but is unassigned in _chapters.json",
            )
        elif count > 1:
            errors.append(
                f"L1: fact {fid!r} assigned {count} times (must be exactly once, "
                "whether within one chapter or across multiple)",
            )
    return errors


def check_l3(
    facts: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
) -> list[str]:
    """Legal placement: fact.lens_tags ∩ chapter.anchor_lenses ≠ ∅, and
    form_lens ∈ fact.lens_tags (the cross-file half deferred by M1 §3.4)."""
    errors: list[str] = []
    facts_by_id = _facts_by_id(facts)

    for chapter in chapters:
        if chapter.get("op") == "drop":
            continue
        cid = chapter.get("id")
        anchor_set = set(chapter.get("anchor_lenses", []))
        for fact_ref in chapter.get("facts", []):
            fid = fact_ref.get("fid")
            fact = facts_by_id.get(fid)
            if fact is None:
                continue  # unknown-id already reported by L1
            tags = set(fact.get("lens_tags", []))
            if not (tags & anchor_set):
                errors.append(
                    f"L3: fact {fid!r} lens_tags {sorted(tags)} do not intersect "
                    f"chapter {cid!r} anchor_lenses {sorted(anchor_set)}",
                )
            form_lens = fact_ref.get("form_lens")
            if form_lens not in tags:
                errors.append(
                    f"L3: fact {fid!r} form_lens {form_lens!r} not in its own "
                    f"lens_tags {sorted(tags)}",
                )
    return errors


def check_l4(chapters: list[dict[str, Any]]) -> list[str]:
    """No rendered (non-drop) chapter has zero facts; drop chapters must be empty.

    Structurally same invariant as ``chapters_schema.validate_chapters`` —
    kept here too as defense-in-depth for callers that construct/mutate a
    chapters list without going through ``validate_chapters``."""
    errors: list[str] = []
    for chapter in chapters:
        cid = chapter.get("id")
        op = chapter.get("op")
        facts_here = chapter.get("facts", [])
        if op == "drop":
            if facts_here:
                errors.append(f"L4: dropped chapter {cid!r} must have empty facts")
        elif not facts_here:
            errors.append(f"L4: rendered chapter {cid!r} has zero facts (empty chapter)")
    return errors


def check_l5(
    chapters: list[dict[str, Any]],
    *,
    candidate_ids: list[str] | None = None,
) -> list[str]:
    """Chapter genealogy reachability: derived_from ⊆ static candidates.

    ``candidate_ids`` comes from the outline-registry static candidate set
    (design §3.3), an M3 deliverable. Defensive default (M3 not ready yet):
    when ``candidate_ids`` is ``None``, this check is skipped entirely."""
    if candidate_ids is None:
        return []
    allowed = set(candidate_ids)
    errors: list[str] = []
    for chapter in chapters:
        cid = chapter.get("id")
        derived = chapter.get("derived_from", [])
        if not derived:
            errors.append(
                f"L5: chapter {cid!r} has no derived_from (orphan; unreachable "
                "from static candidates)",
            )
            continue
        unknown = [d for d in derived if d not in allowed]
        if unknown:
            errors.append(
                f"L5: chapter {cid!r} derived_from references unknown "
                f"candidates {unknown}",
            )
    return errors


def check_c1(
    facts: list[dict[str, Any]],
    *,
    presence_map: dict[str, str] | None = None,
    section_order: list[str] | None = None,
    dependency_graph: dict[str, Any] | None = None,
) -> list[str]:
    """Coverage gate: every ``presence=required`` lens has ≥1 tagging fact;
    ``optional`` + 0 tagging facts is a legal absence (需求2).

    ``presence_map`` / ``section_order`` come from section-registry (an M3
    deliverable for ``presence``). Defensive default: when ``section_order``
    is ``None`` this check is skipped (no lens universe to check against);
    a lens missing from ``presence_map`` defaults to ``required``.

    When ``dependency_graph`` is provided, zero-coverage messages distinguish
    derivation lenses (re-run Step 2→3) from true gaps (Round) — K1 derive design §2.2.
    """
    if section_order is None:
        return []
    # Normalize presence_map keys so callers may pass either case
    # (Grok review Minor#4: raw registry data is not guaranteed upper-case).
    normalized_presence = {
        str(k).strip().upper(): v for k, v in (presence_map or {}).items()
    }
    coverage = lenses_present(facts)
    errors: list[str] = []
    for lens in section_order:
        key = lens.strip().upper()
        presence = normalized_presence.get(key, "required")
        if presence not in ("required", "optional"):
            presence = "required"
        if presence == "required" and coverage.get(key, 0) == 0:
            if dependency_graph is not None:
                from derive_shell import has_derivation  # local import: avoid cycle

                if has_derivation(key, dependency_graph):
                    errors.append(
                        f"C1: required lens {key!r} has zero tagging facts "
                        "(derivation lens — re-run Step 2→3 or Round)",
                    )
                else:
                    errors.append(
                        f"C1: required lens {key!r} has zero tagging facts "
                        "(true gap — no derivation edge; Round)",
                    )
            else:
                errors.append(
                    f"C1: required lens {key!r} has zero tagging facts (coverage gap)",
                )
    return errors


def check_q1(facts: list[dict[str, Any]]) -> dict[str, Any]:
    """Quarantine audit — advisory only, never blocks (no-drop / Eval posture)."""
    ids = unlensed_fact_ids(facts)
    return {"quarantined_ids": ids, "quarantined_total": len(ids)}


def run_display_layer_gates(
    facts: list[dict[str, Any]],
    chapters: list[dict[str, Any]],
    *,
    presence_map: dict[str, str] | None = None,
    section_order: list[str] | None = None,
    candidate_ids: list[str] | None = None,
    dependency_graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all Step 6 gates; return ``{"errors": [...], "q1_audit": {...}}``.

    ``errors`` aggregates L1/L3/L4/L5/C1 (blocking); ``q1_audit`` is
    advisory-only (never contributes to ``errors``)."""
    errors: list[str] = []
    errors.extend(check_l1(facts, chapters))
    errors.extend(check_l3(facts, chapters))
    errors.extend(check_l4(chapters))
    errors.extend(check_l5(chapters, candidate_ids=candidate_ids))
    errors.extend(
        check_c1(
            facts,
            presence_map=presence_map,
            section_order=section_order,
            dependency_graph=dependency_graph,
        ),
    )
    return {
        "errors": errors,
        "q1_audit": check_q1(facts),
    }
