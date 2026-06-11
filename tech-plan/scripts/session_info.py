#!/usr/bin/env python3
"""Read-only session info facade for tech-plan orchestrator.

Aggregates schema modules for SKILL-facing reads. No state mutations.

CLI:
    python3 session_info.py --cycle-id <id> --project-root . [--view delivery-preview|session]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tech_doc_schema import load_presentation_from_cycle  # noqa: E402
from workflow_common import read_md_field, session_base_dir  # noqa: E402
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
)

_VIEW_DELIVERY_PREVIEW = "delivery-preview"
_VIEW_SESSION = "session"
_VALID_VIEWS = frozenset({_VIEW_DELIVERY_PREVIEW, _VIEW_SESSION})


def _active_doc(cycle_id: str, project_root: Path) -> int:
    ss_path = project_root / session_base_dir(cycle_id) / "session-state.md"
    try:
        return int(read_md_field(ss_path, "active_doc", default="1"))
    except ValueError:
        return 1


def delivery_preview(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Return fields needed to present tech-doc before delivery confirmation."""
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    tech_doc = load_presentation_from_cycle(cycle_id, project_root)
    return {
        "view": _VIEW_DELIVERY_PREVIEW,
        "active_doc": _active_doc(cycle_id, project_root),
        "current_state": state["current_state"],
        "tech_doc": {
            "path": tech_doc["path"],
            "title": tech_doc["title"],
            "summary": tech_doc["summary"],
        },
    }


def session_snapshot(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Return workflow state plus tech-doc presentation for session resume."""
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    tech_doc = load_presentation_from_cycle(cycle_id, project_root)
    return {
        "view": _VIEW_SESSION,
        "active_doc": _active_doc(cycle_id, project_root),
        "workflow_state": {
            "current_state": state["current_state"],
            "mode": state.get("mode", ""),
            "evaluate_round": state.get("evaluate_round", "0"),
            "product_ref": state.get("product_ref", ""),
            "carry_forward_ref": state.get("carry_forward_ref", ""),
        },
        "tech_doc": {
            "path": tech_doc["path"],
            "title": tech_doc["title"],
            "summary": tech_doc["summary"],
            "revision": tech_doc["revision"],
        },
    }


def get_session_info(
    cycle_id: str,
    project_root: Path,
    *,
    view: str = _VIEW_DELIVERY_PREVIEW,
) -> dict[str, Any]:
    if view not in _VALID_VIEWS:
        raise ValueError(f"unknown view: {view!r} (allowed: {sorted(_VALID_VIEWS)})")
    if view == _VIEW_SESSION:
        return session_snapshot(cycle_id, project_root)
    return delivery_preview(cycle_id, project_root)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="tech-plan read-only session info")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root directory",
    )
    parser.add_argument(
        "--view",
        choices=sorted(_VALID_VIEWS),
        default=_VIEW_DELIVERY_PREVIEW,
        help="Info slice to return (default: delivery-preview)",
    )
    args = parser.parse_args()

    try:
        payload = get_session_info(
            args.cycle_id.strip(),
            args.project_root.resolve(),
            view=args.view,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
