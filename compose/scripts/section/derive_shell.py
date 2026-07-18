#!/usr/bin/env python3
"""Mechanical shell for kernel Step 3 (deductive derivation, K1).

Design rationale (source repo, why-only): docs/domain/ssot/compose/mechanism-ssot/compose-fact-architecture.md (Pd / source);
process how archive: docs/domain/archive/compose/archive-2.0/compose-fact-first-k1-pd-design.md §2.

Step 3 = AI semantic step + this mechanical shell. Scripts never invent derived
work-item text — they only:
  * decide which required lenses trigger (zero-only + derivation edge);
  * order triggered lenses topologically (upstream-first, cascade-visible);
  * allocate contiguous ``F-(k+1)..`` ids when appending derived facts;
  * run the non-empty self-audit when upstream facts existed (cascade-aware).

Callers pass a dependency-graph subset
(``{"sections": {L: {"upstream": [...], "relations": {...}}}}``) — same shape
as ``section_registry_schema.dependency_graph_subset``. Edge lookup is **pure**
(mirrors ``upstream_edges`` shape) and does not call ``normalize_section`` /
active registry (unit-testable with hand-built graphs).
"""

from __future__ import annotations

from typing import Any

from facts_schema import filter_by_lens, lenses_present, normalize_fact

_DERIVATION_RELATIONS = frozenset({"decompose", "instantiate"})


def _upper(key: str) -> str:
    return str(key).strip().upper()


def normalize_dependency_graph(graph: dict[str, Any]) -> dict[str, Any]:
    """Uppercase section keys / upstreams / relation keys; lowercase relation values."""
    sections_out: dict[str, dict[str, Any]] = {}
    for key, entry in (graph.get("sections") or {}).items():
        if not isinstance(entry, dict):
            continue
        k = _upper(key)
        upstream = [_upper(u) for u in (entry.get("upstream") or [])]
        relations = {
            _upper(rk): str(rv).strip().lower()
            for rk, rv in (entry.get("relations") or {}).items()
        }
        sections_out[k] = {"upstream": upstream, "relations": relations}
    out: dict[str, Any] = {"sections": sections_out}
    if "version" in graph:
        out["version"] = graph["version"]
    return out


def _edges(graph: dict[str, Any], lens: str) -> list[dict[str, str]]:
    """Return upstream edges for ``lens`` (pure mirror of ``upstream_edges``)."""
    g = normalize_dependency_graph(graph)
    key = _upper(lens)
    entry = (g.get("sections") or {}).get(key)
    if not isinstance(entry, dict):
        return []
    edges: list[dict[str, str]] = []
    relations = entry.get("relations") or {}
    for upstream in entry.get("upstream") or []:
        u = _upper(str(upstream))
        relation = str(relations.get(u, "operationalize")).strip().lower()
        edges.append({"upstream_section": u, "upstream_relation": relation})
    return edges


def has_derivation(lens: str, graph: dict[str, Any]) -> bool:
    """True when ``lens`` has at least one decompose/instantiate upstream edge."""
    return any(
        e["upstream_relation"] in _DERIVATION_RELATIONS for e in _edges(graph, lens)
    )


def derivation_upstreams(lens: str, graph: dict[str, Any]) -> list[str]:
    """Upstream lenses reached by decompose/instantiate only (order preserved)."""
    seen: set[str] = set()
    out: list[str] = []
    for edge in _edges(graph, lens):
        if edge["upstream_relation"] not in _DERIVATION_RELATIONS:
            continue
        u = edge["upstream_section"]
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def derive_triggers(
    section_order: list[str],
    presence_map: dict[str, str],
    facts: list[dict[str, Any]],
    graph: dict[str, Any],
) -> list[str]:
    """Lenses that trigger Step 3 (zero-only): required ∧ 0 facts ∧ has derivation.

    Partial coverage (facts > 0) never triggers — intentional I2d regression
    (K1 design §2.2 zero-only). Order follows ``section_order``.
    """
    coverage = lenses_present(facts)
    normalized_presence = {
        _upper(k): str(v).strip().lower() for k, v in (presence_map or {}).items()
    }
    triggered: list[str] = []
    for lens in section_order:
        key = _upper(lens)
        presence = normalized_presence.get(key, "required")
        if presence not in ("required", "optional"):
            presence = "required"
        if presence != "required":
            continue
        if coverage.get(key, 0) != 0:
            continue
        if not has_derivation(key, graph):
            continue
        triggered.append(key)
    return triggered


def true_coverage_gaps(
    section_order: list[str],
    presence_map: dict[str, str],
    facts: list[dict[str, Any]],
    graph: dict[str, Any],
) -> list[str]:
    """Required ∧ 0 facts ∧ **no** derivation edge — Step 3 must not invent."""
    coverage = lenses_present(facts)
    normalized_presence = {
        _upper(k): str(v).strip().lower() for k, v in (presence_map or {}).items()
    }
    gaps: list[str] = []
    for lens in section_order:
        key = _upper(lens)
        presence = normalized_presence.get(key, "required")
        if presence not in ("required", "optional"):
            presence = "required"
        if presence != "required":
            continue
        if coverage.get(key, 0) != 0:
            continue
        if has_derivation(key, graph):
            continue
        gaps.append(key)
    return gaps


def classify_zero_required_lenses(
    section_order: list[str],
    presence_map: dict[str, str],
    facts: list[dict[str, Any]],
    graph: dict[str, Any],
) -> dict[str, list[str]]:
    """Split zero-coverage required lenses into derivation vs true-gap buckets.

    Used by Step 6 routing (re-run Step 2→3 vs Round) and to enrich C1 messages.
    """
    coverage = lenses_present(facts)
    normalized_presence = {
        _upper(k): str(v).strip().lower() for k, v in (presence_map or {}).items()
    }
    derivation: list[str] = []
    true_gaps: list[str] = []
    for lens in section_order:
        key = _upper(lens)
        presence = normalized_presence.get(key, "required")
        if presence not in ("required", "optional"):
            presence = "required"
        if presence != "required":
            continue
        if coverage.get(key, 0) != 0:
            continue
        if has_derivation(key, graph):
            derivation.append(key)
        else:
            true_gaps.append(key)
    return {"derivation": derivation, "true_gaps": true_gaps}


class DeriveCycleError(ValueError):
    """Raised when derivation edges among triggered lenses form a cycle."""


def topo_order_triggered(
    triggered: list[str],
    graph: dict[str, Any],
) -> list[str]:
    """Upstream-first order among ``triggered`` lenses; raise on cycle.

    Only edges whose both ends are in ``triggered`` constrain order. A lens
    that derives from a non-triggered upstream is free to run whenever (its
    upstream facts already exist from Step 2 / earlier Step 3).
    """
    nodes = [_upper(t) for t in triggered]
    node_set = set(nodes)
    preds: dict[str, set[str]] = {n: set() for n in nodes}
    succs: dict[str, set[str]] = {n: set() for n in nodes}
    for n in nodes:
        for u in derivation_upstreams(n, graph):
            if u in node_set:
                preds[n].add(u)
                succs[u].add(n)

    ready = [n for n in nodes if not preds[n]]
    ready.sort(key=lambda x: nodes.index(x))
    ordered: list[str] = []
    remaining_preds = {n: set(ps) for n, ps in preds.items()}

    while ready:
        n = ready.pop(0)
        ordered.append(n)
        for s in sorted(succs[n], key=lambda x: nodes.index(x)):
            remaining_preds[s].discard(n)
            if not remaining_preds[s] and s not in ordered and s not in ready:
                ready.append(s)
                ready.sort(key=lambda x: nodes.index(x))

    if len(ordered) != len(nodes):
        stuck = [n for n in nodes if n not in ordered]
        raise DeriveCycleError(
            f"Step 3 derivation cycle among triggered lenses: {stuck}",
        )
    return ordered


def next_fact_id(facts: list[dict[str, Any]]) -> int:
    """Next contiguous F-n index (1-based) after existing facts."""
    return len(facts) + 1


def append_derived_facts(
    facts: list[dict[str, Any]],
    derived: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Append derived facts with contiguous ``F-(k+1)..`` ids.

    Each item in ``derived`` must supply ``text``, ``lens_tags``, and may
    supply ``source``. Ids in ``derived`` are ignored and reassigned.

    Anchors are inherited mechanically (P4 init-fidelity): a derived fact's
    ``anchors`` = union of the anchors of the upstream facts named in its
    ``source`` (deduped by normalize_fact). Cascade-aware — later derived facts
    can inherit from earlier ones in the same batch.
    """
    out = [normalize_fact(f) for f in facts]
    n = next_fact_id(out)
    anchors_by_id: dict[str, list[dict[str, Any]]] = {
        f["id"]: f.get("anchors", []) for f in out
    }
    for item in derived:
        entry: dict[str, Any] = {
            "id": f"F-{n}",
            "text": item["text"],
            "lens_tags": item["lens_tags"],
        }
        if "source" in item and item["source"] is not None:
            entry["source"] = item["source"]
            inherited = [
                anchor
                for sid in item["source"]
                for anchor in anchors_by_id.get(str(sid).strip(), [])
            ]
            if inherited:
                entry["anchors"] = inherited
        normalized = normalize_fact(entry)
        out.append(normalized)
        anchors_by_id[normalized["id"]] = normalized.get("anchors", [])
        n += 1
    return out


def upstream_fact_count(
    facts: list[dict[str, Any]],
    lens: str,
    graph: dict[str, Any],
) -> int:
    """Count of facts tagged with any derivation-upstream of ``lens``."""
    total = 0
    for u in derivation_upstreams(lens, graph):
        total += len(filter_by_lens(facts, u))
    return total


def check_derive_nonempty_self_audit(
    facts_before: list[dict[str, Any]],
    facts_after: list[dict[str, Any]],
    triggered: list[str],
    graph: dict[str, Any],
) -> list[str]:
    """When upstream has facts in the **after** working set, each triggered
    lens must gain ≥1 new fact (cascade-aware).

    Grok K1 impl review Major: counting upstream on ``facts_before`` missed
    same-pass Step 3 appends (SK derived mid-pass → T still silent). Upstream
    emptiness is therefore judged on ``facts_after``; novelty still uses
    ``before_ids``.

    ``待决`` facts still count (they are real facts with ``lens_tags=[L]``).
    Empty-upstream triggers are skipped (C1 backstop).
    """
    before_ids = {f["id"] for f in facts_before}
    errors: list[str] = []
    for lens in triggered:
        key = _upper(lens)
        if upstream_fact_count(facts_after, key, graph) == 0:
            continue
        new_for_lens = [
            f
            for f in facts_after
            if f["id"] not in before_ids and key in f.get("lens_tags", [])
        ]
        if not new_for_lens:
            errors.append(
                f"Step 3 self-audit: lens {key!r} had non-empty upstream facts "
                "but Step 3 emitted no derived fact (and no 待决 fact)",
            )
    return errors
