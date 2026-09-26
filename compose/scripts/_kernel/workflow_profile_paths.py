"""Profile-aware cache paths for compose stage shells."""

from __future__ import annotations

from pathlib import Path

from workflow_paths import (
    DEFAULT_COMPOSE_PROFILE_ID,
    compose_session_base,
    load_profile,
)


def session_base_dir(
    cycle_id: str,
    profile_id: str,
    project_root: Path,
) -> Path:
    base = compose_session_base(project_root.resolve(), cycle_id, profile_id)
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
    """Inductive state bundle root: active slice under revision{active_doc}/."""
    from l_ledger_schema import active_slice_dir  # noqa: WPS433
    from session_state_schema import load_active_doc_from_cycle  # noqa: WPS433

    active_doc = load_active_doc_from_cycle(cycle_id, project_root, profile_id=profile_id)
    rev = doc_dir(cycle_id, active_doc, profile_id, project_root)
    # active_slice_dir expects an absolute/existing-capable path; resolve via root
    slice_abs = active_slice_dir(project_root.resolve() / rev)
    try:
        return slice_abs.relative_to(project_root.resolve())
    except ValueError:
        return Path(slice_abs)


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
    rev = doc_dir(cycle_id, doc_round, profile_id, project_root)
    from l_ledger_schema import active_slice_dir  # noqa: WPS433

    slice_abs = active_slice_dir(project_root.resolve() / rev)
    try:
        slice_rel = slice_abs.relative_to(project_root.resolve())
    except ValueError:
        slice_rel = Path(slice_abs)
    return slice_rel / filename


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
    """Legacy revision-root evaluate directory (relative to project root)."""
    return doc_dir(cycle_id, doc_round, profile_id, project_root) / f"evaluate{evaluate_round}"


def evaluate_state_path(
    cycle_id: str,
    active_doc: int,
    profile_id: str,
    project_root: Path,
) -> Path:
    """Legacy revision-root evaluate-state.md (relative to project root)."""
    return doc_dir(cycle_id, active_doc, profile_id, project_root) / "evaluate-state.md"


def eval_layout_for_revision(revision_dir: Path) -> str:
    """Always per-L. ``revision_dir`` is unused (hard-cut: no legacy-root)."""
    del revision_dir
    return "per-l"


def evaluate_state_path_for_layout(
    cycle_id: str,
    active_doc: int,
    profile_id: str,
    project_root: Path,
    *,
    layout: str,
    focus_l: str,
) -> Path:
    """evaluate-state.md relative path (always per-L)."""
    del layout
    rev = doc_dir(cycle_id, active_doc, profile_id, project_root)
    return rev / focus_l / "evaluate-state.md"


def eval_round_dir_for_layout(
    cycle_id: str,
    doc_round: int,
    evaluate_round: int,
    profile_id: str,
    project_root: Path,
    *,
    layout: str,
    focus_l: str,
) -> Path:
    """evaluate{M}/ relative path (always per-L)."""
    del layout
    rev = doc_dir(cycle_id, doc_round, profile_id, project_root)
    return rev / focus_l / f"evaluate{evaluate_round}"
