#!/usr/bin/env python3
"""Helpers for entering Evaluating at the adapter boundary (eval + compose state)."""

from __future__ import annotations

from pathlib import Path

from evaluate_state_ops import init_evaluate_state_for_corpus
from workflow_adapter import WorkflowAdapter


def init_evaluate_state_for_session(
    adapter: WorkflowAdapter,
    cycle_id: str,
    project_root: Path,
) -> Path:
    """Initialize evaluate-state.md for the adapter's active revision."""
    es_path = adapter.resolve_evaluate_state_path(cycle_id, project_root)
    corpus = adapter.resolve_eval_corpus(cycle_id, project_root)
    cycle_type = adapter.detect_cycle_type(cycle_id)
    init_evaluate_state_for_corpus(es_path, corpus, cycle_type=cycle_type)
    return es_path
