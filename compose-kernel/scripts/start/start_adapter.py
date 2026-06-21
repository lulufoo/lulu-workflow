#!/usr/bin/env python3
"""Start port for compose orchestrators — dependency inversion."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from delivered_refs_schema import DeliveredRef


class StartAdapter(Protocol):
    """Profile-specific start validation and delivered-ref snapshot rules."""

    def validate_for_start(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
        carry_forward_ref: str = "",
    ) -> list[str]:
        """Return validation errors; empty means ok."""

    def resolve_delivered_refs(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
    ) -> list[DeliveredRef]:
        """Read delivered-refs.json and return snapshot for workflow-state."""

    def resolve_scope_refs(
        self,
        *,
        delivered_refs: list[DeliveredRef],
        run_mode: str = "tech",
        carry_forward_ref: str = "",
    ) -> list[DeliveredRef]:
        """Ordered scope SSOT refs: [0]=primary; [1]+ optional attachments (unused by kernel v1)."""

    def post_start_guidance(
        self,
        *,
        run_mode: str,
        carry_forward_ref: str,
        scope_refs: list[DeliveredRef],
    ) -> str:
        """Orchestrator-facing note after init_drafting (may be empty)."""

    def delivered_ref_for_init(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> DeliveredRef | None:
        """Return primary scope ref (scope_refs[0]) from workflow-state snapshot."""


def primary_scope_from_workflow(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> DeliveredRef | None:
    """Read scope_refs[0] from active revision workflow-state."""
    from compose_session import workflow_state_path  # noqa: WPS433
    from delivered_refs_schema import primary_scope_ref_from_state  # noqa: WPS433
    from workflow_state_schema import load_workflow_state  # noqa: WPS433

    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    if not ws_path.is_file():
        return None
    return primary_scope_ref_from_state(load_workflow_state(ws_path))
