#!/usr/bin/env python3
"""Workflow port for eval_control — consumer-side Protocol (dependency inversion)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class SessionContext:
    """Workflow session facts required to bind EvalCorpus placeholders."""

    active_doc: int
    mode: str
    upstream_baseline_ref: str
    cycle_type: str
    focus_phase: str = "pending"


class WorkflowAdapter(Protocol):
    """Port implemented by each workflow (e.g. lulu-plan, lulu-decision).

    Probe-only adapters implement this contract. Mutation lives on
    FullRemediationAdapter and is required only for full-remediation.
    """

    def resolve_workflow_state_path(
        self, cycle_id: str, project_root: Path
    ) -> Path: ...

    def load_workflow_state(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, str]: ...

    def save_workflow_state(
        self,
        cycle_id: str,
        project_root: Path,
        updates: dict[str, str],
        *,
        merge: bool = True,
    ) -> None: ...

    def resolve_evaluate_state_path(
        self, cycle_id: str, project_root: Path
    ) -> Path: ...

    def session_context(
        self, cycle_id: str, project_root: Path
    ) -> SessionContext: ...

    def eval_paths(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        active_doc: int,
        evaluate_round: int,
        es_path: Path,
    ) -> dict[str, str]: ...

    def corpus_ref_for_mode(self, mode: str) -> str: ...

    def resolve_eval_corpus(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, Any]: ...

    def dimension_defs_dir(self) -> Path: ...

    def corpus_bind_extensions(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, str]: ...

    def detect_cycle_type(self, cycle_id: str) -> str: ...

    def enter_evaluating(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, Any]: ...

    def request_eval_handoff(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        require_evaluating: bool = True,
    ) -> dict[str, Any]: ...

    def commit_eval_artifacts(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        manifest: dict[str, Any],
    ) -> dict[str, Any]: ...

    def commit_evaluate_state(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        staged_state_path: Path,
        set_phase_evaluating: bool = False,
        previous_done_required: bool = False,
    ) -> dict[str, Any]: ...

    def read_eval_target_digest(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        target_path: Path,
    ) -> str: ...

    def discard_eval_staging(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        lease_id: str,
    ) -> dict[str, Any]: ...


class FullRemediationAdapter(WorkflowAdapter, Protocol):
    """full-remediation port: commit and restore EvalTarget."""

    def commit_eval_target(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        staged_target_path: Path,
        base_digest: str,
        lease_id: str,
    ) -> dict[str, Any]: ...

    def restore_eval_target(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        snapshot_path: Path,
        expected_current_digest: str,
        lease_id: str,
    ) -> dict[str, Any]: ...
