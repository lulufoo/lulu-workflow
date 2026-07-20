#!/usr/bin/env python3
"""Shared hard-gate checks for deductive-runner confirm exit.

Fails when:
1. ``deductive-pending.json`` is missing (must run ``pending-init``)
2. Any pending item is still ``open``
3. Quarantined facts with empty ``lens_tags`` are unreferenced AND not settled
   via a non-open ``quarantine_unref`` pending item whose ``upstream_ref`` is
   that fact id
"""

from __future__ import annotations

from pathlib import Path

from deductive_pending_schema import (  # noqa: E402
    load_pending,
    open_items,
    pending_path,
)
from derive_shell import collect_ref_tokens  # noqa: E402
from facts_schema import facts_path, load_facts, unlensed_fact_ids  # noqa: E402

_SETTLED = frozenset({"resolved", "escalated", "out_of_scope"})


def _unreferenced_quarantine_ids(revision_dir: Path) -> list[str]:
    facts = load_facts(facts_path(revision_dir))
    cited: set[str] = set()
    for fact in facts:
        cited |= collect_ref_tokens(fact)
    return [fid for fid in unlensed_fact_ids(facts) if fid not in cited]


def _settled_quarantine_refs(pending_data: dict) -> set[str]:
    settled: set[str] = set()
    for item in pending_data.get("items") or []:
        if str(item.get("kind", "")).strip().lower() != "quarantine_unref":
            continue
        if str(item.get("status", "")).strip().lower() not in _SETTLED:
            continue
        ref = str(item.get("upstream_ref", "")).strip()
        if ref:
            settled.add(ref)
    return settled


def evaluate_deductive_gate(revision_dir: Path) -> str | None:
    """Return a failure reason string, or ``None`` when the confirm gate is clear."""
    rev = Path(revision_dir).resolve()
    facts = facts_path(rev)
    if not facts.is_file():
        return f"_facts.json missing (expected {facts.as_posix()})"

    path = pending_path(rev)
    if not path.is_file():
        return (
            f"deductive-pending.json missing (run pending-init; "
            f"expected {path.as_posix()})"
        )

    data = load_pending(path)
    opens = open_items(data)
    if opens:
        ids = ", ".join(str(i.get("id")) for i in opens)
        return f"open deductive pending remain: {ids}"

    try:
        unref = _unreferenced_quarantine_ids(rev)
    except ValueError as exc:
        return str(exc)
    unsettled = [fid for fid in unref if fid not in _settled_quarantine_refs(data)]
    if unsettled:
        return (
            "unreferenced quarantine not settled "
            f"(cite, or pending-add quarantine_unref then resolve): "
            f"{', '.join(unsettled)}"
        )
    return None
