"""Resolve a decision holder's ``context.docs`` map (shared kernel utility).

Used by stage-owned resolver scripts (``lulu-approach/scripts/resolve_context.py``,
``lulu-bet/scripts/resolve_context.py``) to build the fully resolved ``context``
payload *before* handing it to ``decision`` — decision itself never imports this
module or calls ``get_topic_ref``/``_find_delivered_doc``; it only stores and
reads whatever it is given via ``--domain-constraints-file``.

Both kinds of lookup are derived entirely from ``(cycle_id, stage)`` — nothing
here reads a holder's ``constraints-*.json`` template:

- same-cycle prior stage delivered doc: predecessor from ``transition-table.json``
  + that stage's ``compose-profile.json`` document filename
- cross-cycle topic baseline: ``topic_doc_stage`` + feature ``topic_id``

Output shape (archive-1.1 bind context map): ``{"docs": {key: abs_path, ...}}``.
Only existing files are included; missing docs omit the key (no ``not_found``).
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

# Predecessor / topic stage → self-describing context_docs key.
_STAGE_DOC_KEY: dict[str, str] = {
    "lulu-spec": "product_spec",
    "lulu-arch": "tech_arch",
    "lulu-blueprint": "product_blueprint",
}


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
    """Topic-line doc type this feature-line stage should reference, or None."""
    return _load_transition_table().get("topic_doc_stage", {}).get(stage)


def _upstream_doc_filename(stage: str) -> str | None:
    """The delivered doc filename declared in ``stage``'s own compose-profile.json."""
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


def _doc_key_for_stage(stage: str) -> str | None:
    return _STAGE_DOC_KEY.get(stage)


def build_context_loading(
    cycle_id: str,
    stage: str,
    *,
    cache_dir: Path,
) -> dict[str, Any]:
    """Resolve a holder's ``context`` block as ``{"docs": {key: path}}``.

    Called only by a stage's own resolver script (never by ``decision``).
    Only paths that exist on disk are included; absent docs omit the key.
    """
    cycle_type = cycle_type_from_id(cycle_id)
    docs: dict[str, str] = {}

    pred_stage = _predecessor_stage(cycle_type, stage)
    if pred_stage is not None:
        doc_filename = _upstream_doc_filename(pred_stage)
        doc_key = _doc_key_for_stage(pred_stage)
        if doc_filename is not None and doc_key is not None:
            resolved = _find_delivered_doc(cache_dir, cycle_id, pred_stage, doc_filename)
            if resolved is not None:
                docs[doc_key] = resolved.resolve().as_posix()

    if cycle_type == "feature":
        ref_stage = _topic_doc_stage_for(stage)
        if ref_stage is not None:
            doc_key = _doc_key_for_stage(ref_stage)
            if doc_key is not None:
                ref = get_topic_ref(cycle_id, stage, cache_dir)
                if ref and Path(ref["path"]).is_file():
                    docs[doc_key] = str(Path(ref["path"]).resolve())

    return {"docs": docs}


__all__ = ["build_context_loading"]
