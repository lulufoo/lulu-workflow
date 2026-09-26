#!/usr/bin/env python3
"""Per-command context and locked state mutation shared by execution commands."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

import execution_dispatch as dispatch  # noqa: E402
from compose_session import load_active_doc_for_profile  # noqa: E402
from execution_state_schema import (  # noqa: E402
    execution_dir,
    execution_state_path,
    load_execution_state,
    save_execution_state,
)
from execution_transitions import IllegalTransitionError  # noqa: E402
from revision_lock import LockTimeoutError, revision_lock  # noqa: E402
from session_state_schema import load_session_state  # noqa: E402
from workflow_profile_paths import doc_dir, session_state_path  # noqa: E402
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
)

Apply = Callable[[dict[str, Any]], dict[str, Any]]


def success(command: str, **extra: Any) -> dict[str, Any]:
    return {"ok": True, "command": command, **extra}


def failure(command: str, code: str, error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "command": command, "code": code, "error": error, **extra}


@dataclass(frozen=True)
class ExecutionContext:
    cycle_id: str
    project_root: Path
    profile_id: str
    revision_dir: Path
    execution_dir: Path
    pipeline: dict[str, Any]

    @classmethod
    def build(cls, cycle_id: str, project_root: Path, profile_id: str) -> ExecutionContext:
        active_doc = load_active_doc_for_profile(cycle_id, project_root, profile_id)
        revision_dir = (
            project_root / doc_dir(cycle_id, active_doc, profile_id, project_root)
        ).resolve()
        return cls(
            cycle_id=cycle_id,
            project_root=project_root,
            profile_id=profile_id,
            revision_dir=revision_dir,
            execution_dir=execution_dir(revision_dir),
            pipeline=dispatch.pipeline_config(cycle_id, project_root, profile_id),
        )

    @property
    def inductive(self) -> bool:
        return self.pipeline.get("inductive") is True

    @property
    def freeedit(self) -> bool:
        return self.pipeline.get("freeedit") is True

    def fact_intake_dispatch(self) -> str:
        return dispatch.format_fact_intake_dispatch(
            self.cycle_id,
            self.project_root,
            self.profile_id,
            inductive=self.inductive,
            revision_dir=self.revision_dir,
        )

    def producer_dispatch(self, *, inductive: bool) -> str:
        return dispatch.format_producer_dispatch(
            self.cycle_id,
            self.project_root,
            self.profile_id,
            inductive=inductive,
            revision_dir=self.revision_dir,
        )

    def writing_dispatch(self) -> str:
        return dispatch.format_writing_dispatch(
            self.cycle_id, self.project_root, self.profile_id, self.revision_dir
        )


def require_working(command: str, ctx: ExecutionContext) -> dict[str, Any] | None:
    """Fail unless the session is Working (Delivery / Invalidated freeze execution)."""
    try:
        ws_path = resolve_workflow_state_path_from_cycle(
            ctx.cycle_id, ctx.project_root, profile_id=ctx.profile_id
        )
        if not ws_path.is_file():
            raise FileNotFoundError("workflow-state.md not found (run start first)")
        current = str(load_workflow_state(ws_path)["current_state"]).strip()
    except (OSError, ValueError) as exc:
        return failure(command, "wrong_session_state", str(exc))
    if current != "Working":
        return failure(
            command,
            "wrong_session_state",
            f"session current_state is {current!r} (expected Working)",
            session_state=current,
        )
    try:
        ss_path = ctx.project_root / session_state_path(
            ctx.cycle_id, ctx.profile_id, ctx.project_root
        )
        if load_session_state(ss_path)["holder_finalized"] is not True:
            return failure(
                command,
                "holder_not_finalized",
                "holder_finalized is false; execution writes are blocked",
            )
    except (OSError, ValueError) as exc:
        return failure(command, "holder_not_finalized", str(exc))
    return None


def mutate(command: str, ctx: ExecutionContext, apply: Apply) -> dict[str, Any]:
    """Apply a step transition under the revision lock and persist it."""
    if not execution_state_path(ctx.revision_dir).is_file():
        return failure(command, "unsupported_revision", "missing execution-state.json")
    try:
        with revision_lock(ctx.revision_dir, exclusive=True):
            new_state = apply(load_execution_state(ctx.revision_dir))
            save_execution_state(ctx.revision_dir, new_state)
            return success(command, state=new_state["state"])
    except LockTimeoutError:
        return failure(command, "lock_timeout", "revision lock timeout")
    except IllegalTransitionError as exc:
        return failure(command, exc.code, str(exc), **exc.extra)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return failure(command, "invalid_execution_state", str(exc))


def current_state(command: str, ctx: ExecutionContext, expected: str) -> str | dict[str, Any]:
    """Return the current step state or a failure when it is not ``expected``."""
    try:
        state = str(load_execution_state(ctx.revision_dir)["state"])
    except (OSError, ValueError) as exc:
        return failure(command, "unsupported_revision", str(exc))
    if state != expected:
        return failure(
            command, "illegal_transition", f"{command} requires {expected}", state=state
        )
    return state
