"""Invalidation hook: cascades Invalidated state to downstream sessions.

Public ``invalidate_downstream`` acquires the cycle exclusive lock.
``invalidate_downstream_under_cycle_lock`` requires the caller already holds it.

Compose stages invalidate only the active session-state v2 revision.
v1 / missing / invalid session-state is skipped with a warning.
Flat decision/bet/approach sessions keep their own state files.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from transition_table import load_stage_order  # noqa: E402
from workflow_sessions import get_sessions  # noqa: E402
from cycle_delivered_refs import remove_delivered_ref  # noqa: E402

_SKILL_ROOT = Path(__file__).resolve().parents[1]
_KERNEL_CORE = _SKILL_ROOT / "compose" / "scripts" / "core"
_KERNEL_SCHEMA_SESSION = _SKILL_ROOT / "compose" / "scripts" / "schema" / "session"
_KERNEL_SCRIPTS = _SKILL_ROOT / "compose" / "scripts"

COMPOSE_STAGES = frozenset(
    {"lulu-arch", "lulu-blueprint", "lulu-design", "lulu-plan", "lulu-spec"}
)


def _ensure_compose_paths() -> None:
    for scripts_dir in (_KERNEL_CORE, _KERNEL_SCHEMA_SESSION, _KERNEL_SCRIPTS):
        s = str(scripts_dir)
        if s not in sys.path:
            sys.path.insert(0, s)


def _set_current_state_line(state_path: Path, value: str) -> None:
    """Rewrite a ``current_state:`` line in a non-compose session file."""
    lines = state_path.read_text(encoding="utf-8").splitlines(keepends=True)
    found = False
    out: list[str] = []
    for line in lines:
        if line.startswith("current_state:"):
            out.append(f"current_state: {value}\n" if line.endswith("\n") else f"current_state: {value}")
            found = True
        else:
            out.append(line)
    if not found:
        warnings.warn(
            f"invalidation skip: no current_state field in {state_path}",
            stacklevel=2,
        )
        return
    state_path.write_text("".join(out), encoding="utf-8")


def _invalidate_flat_session(state_path: Path) -> None:
    if not state_path.is_file():
        return
    _set_current_state_line(state_path, "Invalidated")


def _invalidate_compose_active(
    cycle_id: str,
    stage: str,
    cache_dir: Path,
    project_root: Path,
) -> None:
    _ensure_compose_paths()
    from revision_lock import revision_lock, session_lock  # noqa: WPS433
    from session_state_schema import load_session_state  # noqa: WPS433
    from workflow_state_schema import mark_invalidated  # noqa: WPS433

    session_dir = cache_dir / cycle_id / stage
    ss_path = session_dir / "session-state.md"
    if not ss_path.is_file():
        warnings.warn(
            f"invalidation skip: missing session-state.md for {stage}",
            stacklevel=2,
        )
        return
    try:
        state = load_session_state(ss_path)
    except ValueError as exc:
        warnings.warn(
            f"invalidation skip: invalid session-state for {stage}: {exc}",
            stacklevel=2,
        )
        return
    if int(state.get("version", 0) or 0) != 2:
        warnings.warn(
            f"invalidation skip: session-state v1 for {stage}",
            stacklevel=2,
        )
        return
    active_doc = int(state["active_doc"])
    revision_dir = session_dir / f"revision{active_doc}"
    ws_path = revision_dir / "workflow-state.md"
    with session_lock(session_dir, exclusive=False):
        with revision_lock(revision_dir, exclusive=True):
            remove_delivered_ref(cycle_id, project_root, stage)
            if not ws_path.is_file():
                warnings.warn(
                    f"invalidation skip: missing workflow-state.md for {stage}",
                    stacklevel=2,
                )
                return
            try:
                mark_invalidated(ws_path)
            except ValueError as exc:
                warnings.warn(
                    f"invalidation skip: invalid workflow-state for {stage}: {exc}",
                    stacklevel=2,
                )


def invalidate_downstream_under_cycle_lock(
    cycle_id: str,
    from_stage: str,
    cycle_type: str,
    cache_dir: Path,
    *,
    project_root: Path | None = None,
) -> None:
    """Invalidate downstream sessions. Caller must hold cycle exclusive lock."""
    stages = load_stage_order(cycle_type)
    if from_stage not in stages:
        return
    root = project_root if project_root is not None else cache_dir.parent
    downstream = stages[stages.index(from_stage) + 1 :]
    for stage in downstream:
        if stage in COMPOSE_STAGES:
            _invalidate_compose_active(cycle_id, stage, cache_dir, root)
            continue
        for session in get_sessions(cycle_id, stage, cache_dir):
            if session.state == "Invalidated":
                continue
            if session.state_path and session.state_path.exists():
                _invalidate_flat_session(session.state_path)


def invalidate_downstream(
    cycle_id: str,
    from_stage: str,
    cycle_type: str,
    cache_dir: Path,
    *,
    project_root: Path | None = None,
) -> None:
    """Mark downstream sessions Invalidated. Acquires cycle exclusive lock."""
    _ensure_compose_paths()
    from revision_lock import LockTimeout, cycle_lock  # noqa: WPS433

    cycle_cache = cache_dir / cycle_id
    try:
        with cycle_lock(cycle_cache, exclusive=True):
            invalidate_downstream_under_cycle_lock(
                cycle_id,
                from_stage,
                cycle_type,
                cache_dir,
                project_root=project_root,
            )
    except LockTimeout as exc:
        raise RuntimeError(f"invalidation lock_timeout: {exc}") from exc
