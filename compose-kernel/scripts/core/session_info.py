#!/usr/bin/env python3
"""Read-only session info facade for compose orchestrators.

Aggregates schema modules for SKILL-facing reads. No state mutations.

CLI:
    python3 session_info.py --cycle-id <id> --project-root . \\
        [--profile <profile_id>] \\
        [--view delivery-preview|session|stage-transitions]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_CORE = Path(__file__).resolve().parent
_SCRIPTS = _CORE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, WORKFLOW_SCRIPTS  # noqa: E402

sys.path.insert(0, str(WORKFLOW_SCRIPTS))
from hook_guard import load_transitions  # noqa: E402
from compose_session import (  # noqa: E402
    load_active_doc_for_profile,
    load_document_presentation,
    stage_name,
    workflow_state_path,
)
from workflow_common import detect_cycle_type  # noqa: E402
from delivered_refs_schema import parse_delivered_refs  # noqa: E402
from workflow_state_schema import load_workflow_state  # noqa: E402

_VIEW_DELIVERY_PREVIEW = "delivery-preview"
_VIEW_SESSION = "session"
_VIEW_STAGE_TRANSITIONS = "stage-transitions"
_CMD_DELIVERY_PREVIEW = "delivery-preview"
_EXPECTED_DELIVERY_PREVIEW_STATE = "ReadyForDelivery"
_VALID_VIEWS = frozenset({
    _VIEW_DELIVERY_PREVIEW,
    _VIEW_SESSION,
    _VIEW_STAGE_TRANSITIONS,
})


def _compose_document_view(doc: dict[str, Any]) -> dict[str, Any]:
    """Profile-neutral document presentation (tech-doc or design-doc)."""
    return {
        "path": doc["path"],
        "title": doc["title"],
        "summary": doc["summary"],
    }


def _session_document_view(doc: dict[str, Any]) -> dict[str, Any]:
    """Session resume fields including revision."""
    payload = _compose_document_view(doc)
    payload["revision"] = doc["revision"]
    return payload


def _delivery_preview_failure(current_state: str) -> dict[str, Any]:
    return {
        "ok": False,
        "command": _CMD_DELIVERY_PREVIEW,
        "current_state": current_state,
        "message": (
            f"delivery-preview rejected: current state is {current_state}, "
            f"expected {_EXPECTED_DELIVERY_PREVIEW_STATE}. "
            "Pause execution and wait for user direction."
        ),
    }


def delivery_preview(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Return fields needed to present the compose document before delivery."""
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    current = state["current_state"]
    if current != _EXPECTED_DELIVERY_PREVIEW_STATE:
        return _delivery_preview_failure(current)

    doc = load_document_presentation(cycle_id, project_root, profile_id)
    compose_doc = _compose_document_view(doc)
    return {
        "ok": True,
        "view": _VIEW_DELIVERY_PREVIEW,
        "profile_id": profile_id,
        "active_doc": load_active_doc_for_profile(cycle_id, project_root, profile_id),
        "current_state": current,
        "compose_doc": compose_doc,
    }


def stage_transitions(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Return allowed next stages from transition-table.json for this profile."""
    cycle_type = detect_cycle_type(cycle_id)
    transitions = load_transitions(cycle_type)
    next_stages = sorted(transitions.get(stage_name(profile_id), set()))
    return {"profile_id": profile_id, "next_stages": next_stages}


def session_snapshot(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Return workflow state plus document presentation for session resume."""
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    doc = load_document_presentation(cycle_id, project_root, profile_id)
    compose_doc = _session_document_view(doc)
    return {
        "view": _VIEW_SESSION,
        "profile_id": profile_id,
        "active_doc": load_active_doc_for_profile(cycle_id, project_root, profile_id),
        "workflow_state": {
            "current_state": state["current_state"],
            "mode": state.get("mode", ""),
            "evaluate_round": state.get("evaluate_round", "0"),
            "delivered_refs": [r.to_dict() for r in parse_delivered_refs(state)],
            "carry_forward_ref": state.get("carry_forward_ref", ""),
        },
        "compose_doc": compose_doc,
    }


def get_session_info(
    cycle_id: str,
    project_root: Path,
    *,
    view: str = _VIEW_DELIVERY_PREVIEW,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    if view not in _VALID_VIEWS:
        raise ValueError(f"unknown view: {view!r} (allowed: {sorted(_VALID_VIEWS)})")
    if view == _VIEW_SESSION:
        return session_snapshot(cycle_id, project_root, profile_id=profile_id)
    if view == _VIEW_STAGE_TRANSITIONS:
        return stage_transitions(cycle_id, project_root, profile_id=profile_id)
    return delivery_preview(cycle_id, project_root, profile_id=profile_id)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="compose read-only session info")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root directory",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_COMPOSE_PROFILE_ID,
        help="Compose profile / stage name (default: tech-plan)",
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
            profile_id=args.profile.strip(),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(_cli())
