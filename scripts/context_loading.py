"""Resolve a decision holder's ``context.sources[]`` (shared kernel utility).

Used by stage-owned resolver scripts (``lulu-approach/scripts/resolve_context.py``,
``lulu-bet/scripts/resolve_context.py``) to build the fully resolved ``context``
payload *before* handing it to ``decision`` — decision itself never imports this
module or calls ``get_topic_ref``/``_find_delivered_doc``; it only stores and
reads whatever it is given via ``--domain-constraints-file``.

Both kinds of source are derived entirely from ``(cycle_id, stage)`` — nothing
here reads a holder's ``constraints-*.json`` template, because there is nothing
stage-specific left to declare:

- ``upstream`` (same-cycle prior stage's delivered doc): *which* stage is the
  predecessor comes from ``transition-table.json``'s own transition graph for
  this ``cycle_type`` (the edge whose ``to`` contains ``stage``); its cache
  subdir/doc filename come from that predecessor's own ``compose-profile.json``
  manifest (a stable public config file, not a script — same trust boundary as
  reading ``transition-table.json``).
- ``topic`` (cross-cycle topic-line baseline): comes from ``topic_doc_stage``
  in ``transition-table.json`` + the feature's own ``topic_id``
  (``start_gate.get_topic_ref``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from cycle_schema import cycle_type_from_id
from start_gate import get_topic_ref
from workflow_sessions import parse_frontmatter

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_DIR = _SKILL_ROOT / "config"
_REVISION_PAT = re.compile(r"^(revision|r|s)\d+$")


def _load_transition_table() -> dict[str, Any]:
    return json.loads((_CONFIG_DIR / "transition-table.json").read_text(encoding="utf-8"))


def _predecessor_stage(cycle_type: str, stage: str) -> str | None:
    """The stage whose transition edge points at ``stage`` in this cycle_type, or None.

    Raises if more than one distinct non-null predecessor edge exists — a
    stage can have a null ("entry point") edge alongside one real predecessor
    edge (that is resolved as the predecessor), but two different real
    predecessors would be ambiguous and must not be silently guessed.
    """
    table = _load_transition_table()
    candidates = {
        edge.get("from")
        for edge in table.get(cycle_type, [])
        if stage in edge.get("to", [])
    }
    candidates.discard(None)
    if len(candidates) > 1:
        raise ValueError(
            f"ambiguous predecessor for {cycle_type}/{stage}: {sorted(candidates)} "
            f"— transition-table.json has more than one non-null 'from' edge into "
            f"this stage; context resolution cannot pick one automatically."
        )
    return next(iter(candidates), None)


def _topic_doc_stage_for(stage: str) -> str | None:
    """Topic-line doc type this feature-line stage should reference, or None.

    ``topic_doc_stage`` only ever maps feature-line stages (a topic cycle's
    own lulu-bet/lulu-approach never reference an *outer* topic in this
    system), so callers must only consult this when ``cycle_type == "feature"``.
    """
    return _load_transition_table().get("topic_doc_stage", {}).get(stage)


def _upstream_doc_filename(stage: str) -> str | None:
    """The delivered doc filename declared in ``stage``'s own compose-profile.json.

    Decision holders (lulu-bet/lulu-approach) never appear as another decision
    holder's predecessor in the current transition graph, so a decision-holder
    predecessor (flat layout, decision-doc.md) is intentionally not handled here.
    """
    profile_path = _SKILL_ROOT / stage / "compose-profile.json"
    if not profile_path.is_file():
        return None
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    doc_filename = str((profile.get("document") or {}).get("filename", "")).strip()
    return doc_filename or None


def _find_delivered_doc(
    cache_dir: Path,
    cycle_id: str,
    upstream_cache_subdir: str,
    doc_filename: str,
) -> Path | None:
    stage_dir = cache_dir / cycle_id / upstream_cache_subdir
    if not stage_dir.is_dir():
        return None
    candidates: list[tuple[str, str, Path]] = []
    for rev_dir in sorted(stage_dir.iterdir()):
        if not rev_dir.is_dir() or not _REVISION_PAT.match(rev_dir.name):
            continue
        ws = rev_dir / "workflow-state.md"
        if not ws.is_file():
            continue
        fm = parse_frontmatter(ws.read_text(encoding="utf-8"))
        if fm.get("current_state") != "Delivered":
            continue
        doc = rev_dir / doc_filename
        if doc.is_file():
            candidates.append((fm.get("updated_at", ""), rev_dir.name, doc))
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[0], item[1]))[2]


def build_context_loading(
    cycle_id: str,
    stage: str,
    *,
    cache_dir: Path,
) -> dict[str, Any]:
    """Resolve a holder's ``context`` block, driven entirely by ``(cycle_id, stage)``.

    Called only by a stage's own resolver script (never by ``decision``) — the
    caller hands the result to ``decision`` via ``--domain-constraints-file``, which
    stores it in the session's own domain-constraints.json copy as-is.
    ``resolve-context`` and everything downstream only *reads* that already
    resolved copy; nothing in decision ever calls this again, so a source's
    ``status`` / ``resolved_doc_path`` stay pinned to whatever was resolved at
    init time even if the upstream/topic doc changes mid-session.

    Every source in the returned list has the exact same shape — ``kind``,
    ``status``, ``resolved_doc_path``, ``loaded_message`` — regardless of
    which branch produced it; the lookup parameters used to find the doc
    (cache subdir, doc filename) are internal to this function and never
    appear in the result.

    Returns ``{"sources": [...]}``, or ``{"status": "skipped"}`` when neither
    an upstream predecessor nor a topic mapping applies to this stage.
    """
    cycle_type = cycle_type_from_id(cycle_id)
    sources: list[dict[str, Any]] = []

    pred_stage = _predecessor_stage(cycle_type, stage)
    if pred_stage is not None:
        doc_filename = _upstream_doc_filename(pred_stage)
        if doc_filename is not None:
            resolved = _find_delivered_doc(cache_dir, cycle_id, pred_stage, doc_filename)
            sources.append({
                "kind": "upstream",
                "status": "loaded" if resolved else "not_found",
                "resolved_doc_path": resolved.resolve().as_posix() if resolved else "",
                "loaded_message": (
                    f"Loaded upstream {pred_stage} context for scope and constraints "
                    f"only. Do not use it for role, direction, or acceptance criteria."
                ),
            })

    if cycle_type == "feature":
        ref_stage = _topic_doc_stage_for(stage)
        if ref_stage is not None:
            ref = get_topic_ref(cycle_id, stage, cache_dir)
            sources.append({
                "kind": "topic",
                "status": "loaded" if ref else "not_found",
                "resolved_doc_path": ref["path"] if ref else "",
                "loaded_message": (
                    f"Loaded the topic's {ref_stage} baseline for scope and constraints "
                    f"only. Do not use it for role, decision direction, or acceptance criteria."
                ),
            })

    return {"sources": sources} if sources else {"status": "skipped"}


__all__ = ["build_context_loading"]
