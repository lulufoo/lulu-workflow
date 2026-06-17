#!/usr/bin/env python3
"""Backfill delivered-refs.json from Delivered stage sessions (upstream stages)."""

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
from workflow_common import CACHE_DIR, parse_frontmatter_fields  # noqa: E402

_REVISION_DIR_PAT = re.compile(r"^(revision|r)(\d+)$", re.IGNORECASE)
_FLAT_DIAGNOSTIC_STAGES: dict[str, tuple[str, str]] = {
    "tech-diagnostic": ("tech/diagnostic", "decision-doc.md"),
    "product-diagnostic": ("product/diagnostic", "decision-doc.md"),
}
_COMPOSE_REVISION_STAGES: dict[str, tuple[str, str]] = {
    "product-plan": ("product/plan", "product-doc.md"),
    "tech-design": ("tech/design", "design-doc.md"),
    "tech-plan": ("tech/plan", "tech-doc.md"),
}


def _latest_delivered_revision(stage_dir: Path) -> tuple[int, Path] | None:
    """Return (revision_num, workflow_state_path) for latest Delivered revision."""
    best: tuple[str, int, Path] | None = None
    if not stage_dir.is_dir():
        return None
    for rev_dir in stage_dir.iterdir():
        if not rev_dir.is_dir():
            continue
        match = _REVISION_DIR_PAT.match(rev_dir.name)
        if not match:
            continue
        ws = rev_dir / "workflow-state.md"
        if not ws.is_file():
            continue
        fm = parse_frontmatter_fields(ws.read_text(encoding="utf-8"))
        if fm.get("current_state") != "Delivered":
            continue
        rev_num = int(match.group(2))
        updated_at = fm.get("updated_at", "")
        key = (updated_at, rev_num)
        if best is None or key > (best[0], best[1]):
            best = (updated_at, rev_num, ws)
    if best is None:
        return None
    return best[1], best[2]


def _record_compose_revision_stage(
    cycle_id: str,
    project_root: Path,
    *,
    stage_name: str,
    cache_subdir: str,
    doc_filename: str,
) -> None:
    stage_dir = project_root / CACHE_DIR / cycle_id / Path(cache_subdir)
    latest = _latest_delivered_revision(stage_dir)
    if latest is None:
        return
    rev_num, ws_path = latest
    doc_path = ws_path.parent / doc_filename
    if not doc_path.is_file():
        return
    record_delivered_ref(
        cycle_id,
        project_root,
        delivered_type=stage_name,
        path=str(doc_path.resolve()),
        revision=rev_num,
        profile_id=stage_name,
        source_workflow_state=str(ws_path.resolve()),
    )


def _record_flat_diagnostic_stage(
    cycle_id: str,
    project_root: Path,
    *,
    stage_name: str,
    cache_subdir: str,
    doc_filename: str,
) -> None:
    stage_dir = project_root / CACHE_DIR / cycle_id / Path(cache_subdir)
    session_state = stage_dir / "session-state.md"
    if not session_state.is_file():
        return
    fm = parse_frontmatter_fields(session_state.read_text(encoding="utf-8"))
    if fm.get("current_state") != "Delivered":
        return
    doc_path = stage_dir / doc_filename
    if not doc_path.is_file():
        return
    record_delivered_ref(
        cycle_id,
        project_root,
        delivered_type=stage_name,
        path=str(doc_path.resolve()),
        revision=1,
        profile_id=stage_name,
        source_workflow_state=str(session_state.resolve()),
    )


def backfill_delivered_refs_from_cycle(cycle_id: str, project_root: Path) -> None:
    """Upsert delivered-refs.json entries from Delivered upstream sessions (idempotent)."""
    for stage_name, (subdir, doc_name) in _FLAT_DIAGNOSTIC_STAGES.items():
        _record_flat_diagnostic_stage(
            cycle_id,
            project_root,
            stage_name=stage_name,
            cache_subdir=subdir,
            doc_filename=doc_name,
        )
    for stage_name, (subdir, doc_name) in _COMPOSE_REVISION_STAGES.items():
        _record_compose_revision_stage(
            cycle_id,
            project_root,
            stage_name=stage_name,
            cache_subdir=subdir,
            doc_filename=doc_name,
        )
