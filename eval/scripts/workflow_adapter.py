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
    product_ref: str
    cycle_type: str


class WorkflowAdapter(Protocol):
    """Port implemented by each workflow (e.g. lulu-plan)."""

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

    def resolve_execution_mode(
        self, cycle_id: str, project_root: Path
    ) -> str: ...

    def enter_evaluating(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, Any]: ...
