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

    def delivered_ref_for_init(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> DeliveredRef | None:
        """Return the single DeliveredRef Initializing consumes (v1)."""
