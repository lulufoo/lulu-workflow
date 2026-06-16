"""Shared helpers for start / draft integration tests."""

from __future__ import annotations

from pathlib import Path

from session_state_schema import bump_active_doc
from workflow_common import CACHE_DIR, state_path
from workflow_state_schema import init_drafting


def seed_tech_plan_session(
    project_root: Path,
    *,
    cycle_id: str,
    design_ref: str = "",
    mode: str = "tech",
) -> Path:
    """Seed minimal tech-plan session-state + workflow-state for shell tests."""
    cache_dir = project_root / CACHE_DIR
    (cache_dir / cycle_id / "tech" / "diagnostic").mkdir(parents=True, exist_ok=True)
    (cache_dir / cycle_id / "tech" / "diagnostic" / "decision-doc.md").write_text(
        "# Decision\n",
        encoding="utf-8",
    )
    active_doc = bump_active_doc(cycle_id, project_root)
    ws_path = project_root / state_path(cycle_id, active_doc)
    init_drafting(ws_path, mode=mode, design_ref=design_ref)
    return ws_path
