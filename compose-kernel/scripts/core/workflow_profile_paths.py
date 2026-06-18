"""Profile-aware cache paths for compose stage shells (tech-plan, tech-design, …)."""

from __future__ import annotations

from pathlib import Path

from workflow_common import CACHE_DIR
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, load_profile


def session_base_dir(cycle_id: str, profile_id: str = DEFAULT_COMPOSE_PROFILE_ID) -> Path:
    profile = load_profile(profile_id)
    return CACHE_DIR / cycle_id / profile["cache_subdir"]


def session_state_path(cycle_id: str, profile_id: str = DEFAULT_COMPOSE_PROFILE_ID) -> Path:
    return session_base_dir(cycle_id, profile_id) / "session-state.md"


def doc_dir(cycle_id: str, doc_round: int, profile_id: str = DEFAULT_COMPOSE_PROFILE_ID) -> Path:
    return session_base_dir(cycle_id, profile_id) / f"revision{doc_round}"


def state_path(
    cycle_id: str,
    doc_round: int,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    return doc_dir(cycle_id, doc_round, profile_id) / "workflow-state.md"


def document_path(
    cycle_id: str,
    doc_round: int,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    profile = load_profile(profile_id)
    filename = profile["document"]["filename"]
    return doc_dir(cycle_id, doc_round, profile_id) / filename


def approval_path(
    cycle_id: str,
    doc_round: int,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    return doc_dir(cycle_id, doc_round, profile_id) / "human-delivery-gate.md"


def eval_round_dir(
    cycle_id: str,
    doc_round: int,
    evaluate_round: int,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    return doc_dir(cycle_id, doc_round, profile_id) / f"evaluate{evaluate_round}"


def decision_doc_path(cycle_id: str) -> Path:
    """Diagnostic decision-doc path (shared across compose stages)."""
    return CACHE_DIR / cycle_id / "tech" / "diagnostic" / "decision-doc.md"
