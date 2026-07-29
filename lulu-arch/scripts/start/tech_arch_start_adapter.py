#!/usr/bin/env python3
"""lulu-arch StartAdapter implementation."""

from __future__ import annotations

import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose" / "scripts"
if str(_KERNEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_KERNEL_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from delivered_refs_schema import (  # noqa: E402
    DeliveredRef,
    entry_path_ok,
    load_delivered_refs_file,
    ref_from_file_entry,
)
from start_adapter import primary_scope_from_workflow  # noqa: E402
from start_scope_helpers import first_ref, require_decision_fact_scope  # noqa: E402
from workflow_common import detect_cycle_type  # noqa: E402


class TechArchStartAdapter:
    """Start rules for lulu-arch compose profile (topic cycles only)."""

    def infer_run_mode(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> str:
        del cycle_id, project_root
        return "tech"

    def validate_for_start(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
        carry_forward_ref: str = "",
    ) -> list[str]:
        del carry_forward_ref
        if run_mode not in ("tech",):
            return [f"invalid run_mode: {run_mode!r} (lulu-arch is tech-only)"]
        if detect_cycle_type(cycle_id) != "topic":
            return ["lulu-arch is topic-only; feature cycles are not supported"]
        data = load_delivered_refs_file(cycle_id, project_root)
        if not entry_path_ok(data, "lulu-approach"):
            return ["missing delivered-refs entry: lulu-approach"]
        return []

    def resolve_delivered_refs(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        run_mode: str,
    ) -> list[DeliveredRef]:
        del run_mode
        data = load_delivered_refs_file(cycle_id, project_root)
        ref = ref_from_file_entry("lulu-approach", data)
        if ref is None or not Path(ref.path).is_file():
            return []
        return [ref]

    def resolve_scope_refs(
        self,
        *,
        delivered_refs: list[DeliveredRef],
        run_mode: str = "tech",
        carry_forward_ref: str = "",
        revision_dir: Path | None = None,
    ) -> list[DeliveredRef]:
        """Scope SSOT = lulu-approach decision-fact.json when delivered; else decision-doc."""
        del run_mode, carry_forward_ref, revision_dir
        primary = first_ref(delivered_refs, "lulu-approach")
        if primary is None:
            return []
        return [require_decision_fact_scope(primary)]

    def resolve_intent_baseline_refs(
        self,
        *,
        delivered_refs: list[DeliveredRef],
        run_mode: str = "tech",
    ) -> list[DeliveredRef]:
        del delivered_refs, run_mode
        return []

    def resolve_norm_constraint_refs(
        self,
        *,
        cycle_id: str,
        project_root: Path | None = None,
        delivered_refs: list[DeliveredRef] | None = None,
    ) -> list[DeliveredRef]:
        del cycle_id, project_root, delivered_refs
        return []

    def delivered_ref_for_init(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> DeliveredRef | None:
        return primary_scope_from_workflow(cycle_id, project_root, "lulu-arch")

    def post_start_guidance(
        self,
        *,
        run_mode: str,
        carry_forward_ref: str,
        scope_refs: list[DeliveredRef],
    ) -> str:
        del run_mode, carry_forward_ref, scope_refs
        return (
            "Topic technical architecture stage: pause after Initializing; "
            "then choose FreeEdit, Evaluating (arch-quality), or Deliver."
        )
