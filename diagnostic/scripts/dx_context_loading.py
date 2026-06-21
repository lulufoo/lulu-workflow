#!/usr/bin/env python3
"""Resolve context_loading from domain-constraints config."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from workflow_sessions import parse_frontmatter  # noqa: E402

_REVISION_PAT = re.compile(r"^(revision|r|s)\d+$")


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
    project_root: Path,
    cycle_id: str,
    constraints: dict[str, Any],
    cycle_type: str,
    *,
    cache_dir: Path,
) -> dict[str, Any]:
    """Resolve context_loading block for resolve-context."""
    cfg = constraints.get("context_loading")
    if not isinstance(cfg, dict):
        return {"status": "skipped"}

    sources = cfg.get("sources")
    if not isinstance(sources, list):
        return {"status": "skipped"}

    optional = bool(cfg.get("optional", True))
    for src in sources:
        if not isinstance(src, dict):
            continue
        if str(src.get("cycle_type", "")).strip() != cycle_type:
            continue
        subdir = str(src.get("upstream_cache_subdir", "")).strip()
        doc_name = str(src.get("doc_filename", "")).strip()
        if not subdir or not doc_name:
            continue
        resolved = _find_delivered_doc(cache_dir, cycle_id, subdir, doc_name)
        loaded_message = str(src.get("loaded_message", "")).strip()
        if resolved is not None:
            return {
                "status": "loaded",
                "resolved_doc_path": resolved.resolve().as_posix(),
                "loaded_message": loaded_message,
                "optional": optional,
            }
        return {
            "status": "not_found",
            "resolved_doc_path": "",
            "loaded_message": loaded_message,
            "optional": optional,
        }

    return {"status": "skipped", "optional": optional}
