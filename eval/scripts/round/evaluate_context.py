"""Commit and load evaluating evaluate-state for Eval."""

from __future__ import annotations

import fcntl
from pathlib import Path
from typing import Any, Callable

import eval_control as ec
import session_binding
from evaluate_state_schema import (
    is_v8_state,
    load_evaluate_state,
    parse_frontmatter_fields,
    save_evaluate_state,
)


def _commit_staged_evaluate_state(
    cycle_id: str,
    project_root: Path,
    *,
    patch: dict[str, str] | None = None,
    update: Callable[[dict[str, str]], dict[str, str]] | None = None,
    state: dict[str, str] | None = None,
    state_content: str | None = None,
    set_phase_evaluating: bool = False,
    previous_done_required: bool = False,
) -> str | None:
    """Stage a full evaluate state and publish it through the workflow adapter."""
    paths = session_binding._paths_from_handoff()
    if paths is None:
        ec._refresh_handoff(
            cycle_id,
            project_root,
            require_evaluating=not set_phase_evaluating,
        )
        paths = session_binding._paths_from_handoff()
    if paths is None:
        raise ValueError("EvalHandoff paths missing")

    formal_state_path = Path(paths["evaluate_state"])
    lock_path = formal_state_path.with_suffix(formal_state_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if state_content is not None:
                if state is not None or patch is not None or update is not None:
                    raise ValueError(
                        "state_content cannot be combined with state, patch, or update",
                    )
                next_state = None
            elif state is not None:
                if patch is not None or update is not None:
                    raise ValueError("state cannot be combined with patch or update")
                next_state = dict(state)
            else:
                current_state = load_evaluate_state(formal_state_path)
                if update is not None:
                    next_state = update(current_state)
                else:
                    next_state = dict(current_state)
                    next_state.update(patch or {})

            staged_state_path = Path(paths["write_staging_dir"]) / "evaluate-state.md"
            if state_content is not None:
                ec._atomic_write_text(staged_state_path, state_content)
                load_evaluate_state(staged_state_path)
            else:
                save_evaluate_state(staged_state_path, next_state, merge=False)
            publish = ec._adapter().commit_evaluate_state(
                cycle_id,
                project_root,
                staged_state_path=staged_state_path,
                set_phase_evaluating=set_phase_evaluating,
                previous_done_required=previous_done_required,
            )
            if publish.get("ok"):
                return None
            staged_state_path.unlink(missing_ok=True)
            return str(publish.get("error") or "commit-evaluate-state failed")
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _load_evaluating_context(
    cycle_id: str,
    project_root: Path,
) -> tuple[dict[str, str], Path, dict[str, str], int, int, str] | dict[str, Any]:
    """Return (state, ws_path, eval_data, evaluate_round, active_doc, mode) or failure."""
    ws_path = ec._adapter().resolve_workflow_state_path(cycle_id, project_root)
    state = ec._adapter().load_workflow_state(cycle_id, project_root)
    current = state["current_state"]
    if current != ec._EXPECTED_SESSION_STATE:
        return ec._failure(
            "",
            (
                f"current state is {current!r}, "
                f"expected {ec._EXPECTED_SESSION_STATE!r}."
            ),
            current_state=current,
        )
    phase = session_binding._focus_phase(cycle_id, project_root)
    if phase != ec._EXPECTED_FOCUS_PHASE:
        return ec._failure(
            "",
            (
                f"focus phase is {phase!r}, "
                f"expected {ec._EXPECTED_FOCUS_PHASE!r}."
            ),
            current_state=current,
        )

    es_path = session_binding._evaluate_state_path(cycle_id, project_root)
    if not es_path.exists():
        return ec._failure(
            "",
            "evaluate-state.md not found.",
            current_state=current,
        )

    raw_state = parse_frontmatter_fields(es_path.read_text(encoding="utf-8"))
    if not is_v8_state(raw_state):
        return ec._failure(
            "",
            "incompatible_round: evaluate-state must be v8",
            current_state=current,
        )
    try:
        eval_data = load_evaluate_state(es_path)
    except ValueError as exc:
        return ec._failure("", str(exc), current_state=current)

    evaluate_round = 0
    context = ec._handoff_context()
    if context:
        try:
            evaluate_round = int(context.get("evaluate_round", 0))
        except (TypeError, ValueError):
            evaluate_round = 0
    if evaluate_round < 1:
        try:
            evaluate_round = int(eval_data.get("evaluate_round", "0"))
        except ValueError:
            evaluate_round = 0
    if evaluate_round < 1:
        try:
            evaluate_round = int(state.get("evaluate_round", "0"))
        except ValueError:
            evaluate_round = 0
    if evaluate_round < 1:
        return ec._failure(
            "",
            f"evaluate_round is {evaluate_round!r} (expected >= 1).",
            current_state=current,
        )

    active_doc = ec._adapter().session_context(cycle_id, project_root).active_doc
    mode = state["mode"]
    return state, ws_path, eval_data, evaluate_round, active_doc, mode
