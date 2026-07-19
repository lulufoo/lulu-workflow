#!/usr/bin/env python3
"""Start port for compose orchestrators — dependency inversion.

Provenance reference model (materialized handoff):
    At stage start the resolver settles the three provenance refs ONCE and
    writes them to the per-revision ``resolved-refs.json`` (②). Compose
    consumers read that artifact; they never re-derive from workflow-state or
    from the mutable cycle delivered-refs.json. The ``*_from_workflow`` helpers
    below are thin readers of ②.

    * scope (派生父级)        -> ``resolve_scope_refs`` → ``$SCOPE_REF``
      (decision holders: decision-fact.json required with units; plan→design uses design-doc)
    * intent baseline (意图基准) -> ``resolve_intent_baseline_refs``
    * norm constraint (规范约束) -> ``resolve_norm_constraint_refs``
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Protocol

from delivered_refs_schema import DeliveredRef


class StartAdapter(Protocol):
    """Profile-specific start validation and provenance-ref derivation rules."""

    def infer_run_mode(
        self,
        cycle_id: str,
        project_root: Path,
    ) -> str:
        """Infer run_mode (``product`` or ``tech``) from cycle delivered-refs."""

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
        """派生父级 refs derived from the delivered snapshot ([0]=primary scope)."""

    def resolve_intent_baseline_refs(
        self,
        *,
        delivered_refs: list[DeliveredRef],
        run_mode: str = "tech",
    ) -> list[DeliveredRef]:
        """意图基准 refs derived from the delivered snapshot (may be empty)."""

    def resolve_norm_constraint_refs(
        self,
        *,
        cycle_id: str,
        project_root: Path | None = None,
    ) -> list[DeliveredRef]:
        """规范约束 refs from stage config (may be empty).

        Sole writer of this list, including cross-cycle topic-line refs (see
        ``start_gate.get_topic_ref``) when the profile opts in — the compose
        orchestrator only calls this and persists the result, it never
        appends to it itself.
        """

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
        """Return primary scope ref (scope[0]) derived from workflow-state snapshot."""


def load_start_adapter(profile: dict, profile_json_path: Path) -> StartAdapter:
    """Instantiate the StartAdapter declared by ``profile.start``."""
    start_config = profile.get("start") or {}
    adapter_module = str(start_config.get("adapter_module", "")).strip()
    adapter_class = str(start_config.get("adapter_class", "")).strip()
    if not adapter_module:
        raise ValueError("profile.start.adapter_module is required")
    if not adapter_class:
        raise ValueError("profile.start.adapter_class is required")

    workflow_root = profile_json_path.resolve().parent.parent
    adapter_path = Path(adapter_module)
    if not adapter_path.is_absolute():
        adapter_path = (workflow_root / adapter_path).resolve()
    if not adapter_path.is_file():
        raise ValueError(f"start.adapter_module not found: {adapter_path.as_posix()}")

    module_name = f"_compose_start_adapter_{profile.get('profile_id', profile_json_path.parent.name)}"
    spec = importlib.util.spec_from_file_location(module_name, adapter_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load start.adapter_module: {adapter_path.as_posix()}")

    adapter_dir = str(adapter_path.parent)
    if adapter_dir not in sys.path:
        sys.path.insert(0, adapter_dir)

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter_type = getattr(module, adapter_class, None)
    if adapter_type is None:
        raise ValueError(
            f"adapter class {adapter_class!r} not found in {adapter_path.as_posix()}",
        )
    return adapter_type()


def load_start_adapter_for_profile(profile_id: str) -> StartAdapter:
    """Load the StartAdapter for a profile via its authoring compose-profile.json."""
    from workflow_paths import compose_profile_path, load_profile_json  # noqa: WPS433

    profile_json_path = compose_profile_path(profile_id)
    profile = load_profile_json(profile_json_path)
    return load_start_adapter(profile, profile_json_path)


def _revision_dir_for_workflow(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> Path | None:
    """Return the active revision dir (sibling of workflow-state.md), if present."""
    from compose_session import workflow_state_path  # noqa: WPS433

    revision_dir = workflow_state_path(cycle_id, project_root, profile_id).parent
    return revision_dir if revision_dir.is_dir() else None


def primary_scope_from_workflow(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> DeliveredRef | None:
    """Read scope (派生父级) from the per-revision resolved-refs.json (②)."""
    from resolved_refs_schema import has_resolved_refs, resolved_scope_ref  # noqa: WPS433

    revision_dir = _revision_dir_for_workflow(cycle_id, project_root, profile_id)
    if revision_dir is None or not has_resolved_refs(revision_dir):
        return None
    return resolved_scope_ref(revision_dir)


def intent_baseline_from_workflow(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> list[DeliveredRef]:
    """Read 意图基准 refs from the per-revision resolved-refs.json (②)."""
    from resolved_refs_schema import (  # noqa: WPS433
        has_resolved_refs,
        resolved_intent_baseline_refs,
    )

    revision_dir = _revision_dir_for_workflow(cycle_id, project_root, profile_id)
    if revision_dir is None or not has_resolved_refs(revision_dir):
        return []
    return resolved_intent_baseline_refs(revision_dir)


def norm_constraint_from_workflow(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> list[DeliveredRef]:
    """Read 规范约束 refs from the per-revision resolved-refs.json (②)."""
    from resolved_refs_schema import (  # noqa: WPS433
        has_resolved_refs,
        resolved_norm_constraint_refs,
    )

    revision_dir = _revision_dir_for_workflow(cycle_id, project_root, profile_id)
    if revision_dir is None or not has_resolved_refs(revision_dir):
        return []
    return resolved_norm_constraint_refs(revision_dir)
