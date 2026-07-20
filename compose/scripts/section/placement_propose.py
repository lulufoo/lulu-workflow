#!/usr/bin/env python3
"""C1 mechanical placement proposal (archive-3.0 Step 4.C).

Single-lens facts → ``mechanical`` rows. Multi-lens facts → ``needs_resolution``
for C2 (AI); not written into the draft placement until resolved.
"""

from __future__ import annotations

from typing import Any


def propose_placement(
    facts: list[dict[str, Any]],
    themes: dict[str, Any],
    framework: dict[str, Any],
) -> dict[str, Any]:
    """Build a placement draft from themes + framework topology.

    Returns:
      placement: chapter-placement shaped object (mechanical rows only)
      needs_resolution: multi-lens facts with candidate FL ids
      unmapped_facts: tagged facts with no FL in themes∩framework
      mechanical_total / needs_resolution_total / unmapped_total
    """
    fl_by_key: dict[str, str] = {}
    for entry in themes.get("lens_themes") or []:
        key = str(entry.get("lens_key", "")).strip().upper()
        fl = str(entry.get("form_lens_id", "")).strip()
        if key and fl:
            fl_by_key[key] = fl

    fl_to_chapter: dict[str, str] = {}
    framework_order: list[str] = []
    for chapter in framework.get("chapters") or []:
        cid = str(chapter.get("id", "")).strip()
        if not cid:
            continue
        framework_order.append(cid)
        for fl in chapter.get("anchor_form_lens_ids") or []:
            fl_to_chapter[str(fl).strip()] = cid

    by_chapter: dict[str, list[dict[str, Any]]] = {cid: [] for cid in framework_order}
    needs_resolution: list[dict[str, Any]] = []
    unmapped: list[str] = []

    for fact in facts:
        fid = str(fact.get("id", "")).strip()
        tags = [
            str(t).strip().upper()
            for t in (fact.get("lens_tags") or [])
            if str(t).strip()
        ]
        if not fid or not tags:
            continue

        candidate_fls: list[str] = []
        seen: set[str] = set()
        for key in tags:
            fl = fl_by_key.get(key)
            if not fl or fl not in fl_to_chapter or fl in seen:
                continue
            seen.add(fl)
            candidate_fls.append(fl)

        if not candidate_fls:
            unmapped.append(fid)
        elif len(candidate_fls) == 1:
            fl = candidate_fls[0]
            cid = fl_to_chapter[fl]
            by_chapter[cid].append(
                {
                    "fid": fid,
                    "form_lens_id": fl,
                    "placement": "mechanical",
                }
            )
        else:
            needs_resolution.append(
                {
                    "fid": fid,
                    "candidates": candidate_fls,
                    "lens_tags": tags,
                }
            )

    chapters_out = [
        {"id": cid, "facts": by_chapter[cid]}
        for cid in framework_order
        if by_chapter[cid]
    ]

    placement = {
        "version": "1",
        "$schema_id": "chapter-placement",
        "chapters": chapters_out,
    }
    return {
        "placement": placement,
        "needs_resolution": needs_resolution,
        "unmapped_facts": unmapped,
        "mechanical_total": sum(len(c["facts"]) for c in chapters_out),
        "needs_resolution_total": len(needs_resolution),
        "unmapped_total": len(unmapped),
    }


def themes_coverage_errors(
    themes: dict[str, Any],
    *,
    facts: list[dict[str, Any]] | None = None,
    required_lenses: list[str] | None = None,
    allowed_lenses: list[str] | None = None,
) -> list[str]:
    """Require theme lens_keys ⊇ (fact-present ∩ allowed) ∪ required.

    ``allowed_lenses`` defaults to no filter (all present tags count).
    """
    keys = {
        str(e.get("lens_key", "")).strip().upper()
        for e in (themes.get("lens_themes") or [])
        if str(e.get("lens_key", "")).strip()
    }
    allowed = {
        str(x).strip().upper()
        for x in (allowed_lenses or [])
        if str(x).strip()
    }
    present: set[str] = set()
    for fact in facts or []:
        for tag in fact.get("lens_tags") or []:
            key = str(tag).strip().upper()
            if not key:
                continue
            if allowed and key not in allowed:
                continue
            present.add(key)
    required = {
        str(x).strip().upper()
        for x in (required_lenses or [])
        if str(x).strip()
    }
    needed = present | required
    missing = sorted(needed - keys)
    if missing:
        return [
            "themes coverage gap — missing lens_keys for "
            f"present∪required lenses: {missing}",
        ]
    return []
