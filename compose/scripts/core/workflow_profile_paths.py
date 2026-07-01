"""Profile-aware cache paths for compose stage shells."""

from __future__ import annotations

from pathlib import Path

from workflow_paths import (
    DEFAULT_COMPOSE_PROFILE_ID,
    load_profile,
    resolve_compose_session_base,
)


def session_base_dir(
    cycle_id: str,
    profile_id: str,
    project_root: Path,
) -> Path:
    base = resolve_compose_session_base(project_root.resolve(), cycle_id, profile_id)
    return base.relative_to(project_root.resolve())


def session_state_path(
    cycle_id: str,
    profile_id: str,
    project_root: Path,
) -> Path:
    return session_base_dir(cycle_id, profile_id, project_root) / "session-state.md"


def doc_dir(
    cycle_id: str,
    doc_round: int,
    profile_id: str,
    project_root: Path,
) -> Path:
    return session_base_dir(cycle_id, profile_id, project_root) / f"revision{doc_round}"


def inductive_out_dir(
    cycle_id: str,
    profile_id: str,
    project_root: Path,
) -> Path:
    """Inductive state bundle root: revision{active_doc}/ alongside drafting artifacts."""
    from session_state_schema import load_active_doc_from_cycle  # noqa: WPS433

    active_doc = load_active_doc_from_cycle(cycle_id, project_root, profile_id=profile_id)
    return doc_dir(cycle_id, active_doc, profile_id, project_root)


def state_path(
    cycle_id: str,
    doc_round: int,
    profile_id: str,
    project_root: Path,
) -> Path:
    return doc_dir(cycle_id, doc_round, profile_id, project_root) / "workflow-state.md"


def document_path(
    cycle_id: str,
    doc_round: int,
    profile_id: str,
    project_root: Path,
) -> Path:
    profile = load_profile(profile_id, project_root=project_root, cycle_id=cycle_id)
    filename = profile["document"]["filename"]
    return doc_dir(cycle_id, doc_round, profile_id, project_root) / filename


def approval_path(
    cycle_id: str,
    doc_round: int,
    profile_id: str,
    project_root: Path,
) -> Path:
    return doc_dir(cycle_id, doc_round, profile_id, project_root) / "human-delivery-gate.md"


def eval_round_dir(
    cycle_id: str,
    doc_round: int,
    evaluate_round: int,
    profile_id: str,
    project_root: Path,
) -> Path:
    return doc_dir(cycle_id, doc_round, profile_id, project_root) / f"evaluate{evaluate_round}"


def evaluate_state_path(
    cycle_id: str,
    active_doc: int,
    profile_id: str,
    project_root: Path,
) -> Path:
    """Path to evaluate-state.md for the active revision (relative to project root)."""
    return doc_dir(cycle_id, active_doc, profile_id, project_root) / "evaluate-state.md"
