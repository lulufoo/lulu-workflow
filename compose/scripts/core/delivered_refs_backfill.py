#!/usr/bin/env python3
"""Reconcile delivered-refs.json from Delivered upstream sessions in cache."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parent
_SCRIPTS = _CORE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from delivered_refs_schema import record_delivered_ref  # noqa: E402
from delivery_descriptors import (  # noqa: E402
    DeliveryDescriptor,
    iter_delivery_descriptors,
)
from workflow_common import CACHE_DIR, parse_frontmatter_fields  # noqa: E402

_REVISION_DIR_PAT = re.compile(r"^(revision|r)(\d+)$", re.IGNORECASE)


def _latest_delivered_revision(stage_dir: Path, desc: DeliveryDescriptor) -> tuple[int, Path] | None:
    best: tuple[str, int, Path] | None = None
    if not stage_dir.is_dir():
        return None
    for rev_dir in stage_dir.iterdir():
        if not rev_dir.is_dir():
            continue
        match = _REVISION_DIR_PAT.match(rev_dir.name)
        if not match:
            continue
        ws = rev_dir / desc.state_file
        if not ws.is_file():
            continue
        fm = parse_frontmatter_fields(ws.read_text(encoding="utf-8"))
        if fm.get("current_state") != desc.terminal_state:
            continue
        rev_num = int(match.group(2))
        updated_at = fm.get("updated_at", "")
        key = (updated_at, rev_num)
        if best is None or key > (best[0], best[1]):
            best = (updated_at, rev_num, ws)
    if best is None:
        return None
    return best[1], best[2]


def _record_revision_delivery(
    cycle_id: str,
    project_root: Path,
    desc: DeliveryDescriptor,
) -> None:
    stage_dir = project_root / CACHE_DIR / cycle_id / Path(desc.cache_subdir)
    latest = _latest_delivered_revision(stage_dir, desc)
    if latest is None:
        return
    rev_num, ws_path = latest
    doc_path = ws_path.parent / desc.doc_filename
    if not doc_path.is_file():
        return
    record_delivered_ref(
        cycle_id,
        project_root,
        delivered_type=desc.stage_name,
        path=str(doc_path.resolve()),
        revision=rev_num,
        profile_id=desc.stage_name,
        source_workflow_state=str(ws_path.resolve()),
    )


def _record_flat_delivery(
    cycle_id: str,
    project_root: Path,
    desc: DeliveryDescriptor,
) -> None:
    stage_dir = project_root / CACHE_DIR / cycle_id / Path(desc.cache_subdir)
    state_path = stage_dir / desc.state_file
    if not state_path.is_file():
        return
    fm = parse_frontmatter_fields(state_path.read_text(encoding="utf-8"))
    if fm.get("current_state") != desc.terminal_state:
        return
    doc_path = stage_dir / desc.doc_filename
    if not doc_path.is_file():
        return
    # Decision-holder stages (flat): compose scope SSOT is decision-fact.json
    decision_fact_arg: str | None = None
    decision_fact = stage_dir / "decision-fact.json"
    if decision_fact.is_file():
        decision_fact_arg = str(decision_fact.resolve())
    record_delivered_ref(
        cycle_id,
        project_root,
        delivered_type=desc.stage_name,
        path=str(doc_path.resolve()),
        revision=1,
        profile_id=desc.stage_name,
        source_workflow_state=str(state_path.resolve()),
        decision_fact_path=decision_fact_arg,
    )


def backfill_delivered_refs_from_cycle(cycle_id: str, project_root: Path) -> None:
    """Upsert delivered-refs.json from Delivered upstream cache (idempotent reconcile)."""
    for desc in iter_delivery_descriptors():
        if desc.layout == "revision":
            _record_revision_delivery(cycle_id, project_root, desc)
        else:
            _record_flat_delivery(cycle_id, project_root, desc)
