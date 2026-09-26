#!/usr/bin/env python3
"""Execution step control for compose (``$EXECUTION``).

Subcommands:
    status
    enter-fact-intake / complete-fact-intake
    enter-inductive / complete-inductive
    enter-deductive / complete-deductive
    enter-writing / complete-writing
    enter-freeedit
    reverse-to-inductive / reverse-to-deductive / reverse-to-writing
    enter-evaluating
    accept --confirm / fix --confirm / re-evaluate --confirm / reopen --confirm

Writes ``execution-state.json`` only; session state stays in workflow-state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

import execution_checks as checks  # noqa: E402
import execution_dispatch as dispatch  # noqa: E402
from execution_context import ExecutionContext, failure, require_working, success  # noqa: E402
from execution_eval_entry import (  # noqa: E402, F401
    enter_evaluating_state,
    rollback_evaluating_phase,
)
from execution_handlers import CONFIRM_COMMANDS, HANDLERS  # noqa: E402
from execution_state_schema import execution_state_path, load_execution_state  # noqa: E402
from revision_lock import LockTimeoutError, revision_lock, session_lock  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, resolve_profile_id  # noqa: E402
from workflow_profile_paths import session_state_path  # noqa: E402

derive_step_next_actions = dispatch.derive_step_next_actions


def _status(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    if not execution_state_path(ctx.revision_dir).is_file():
        return failure(command, "unsupported_revision", "missing execution-state.json")
    try:
        with revision_lock(ctx.revision_dir, exclusive=False):
            state = str(load_execution_state(ctx.revision_dir)["state"])
    except LockTimeoutError:
        return failure(command, "lock_timeout", "revision lock timeout")
    except (OSError, ValueError) as exc:
        return failure(command, "invalid_execution_state", str(exc))
    ex = ctx.execution_dir
    inductive_ok = checks.inductive_complete_error(ex) is None
    deductive_ok = checks.deductive_complete_error(ctx.revision_dir, ex) is None
    writing_ok = checks.has_stamp(ex, checks.WRITING_STAMP)
    payload = success(
        command,
        state=state,
        inductive_complete=inductive_ok,
        deductive_complete=deductive_ok,
        writing_complete=writing_ok,
        next_actions=derive_step_next_actions(
            state,
            writing_ok=writing_ok,
            freeedit=ctx.freeedit,
            fact_intake_ok=checks.has_stamp(ex, checks.FACT_INTAKE_STAMP),
            inductive=ctx.inductive,
            inductive_ok=inductive_ok,
            deductive_ok=deductive_ok,
        ),
    )
    eval_run = checks.load_eval_run(ex)
    if eval_run and eval_run.get("eval_run_id"):
        payload["eval_run_id"] = eval_run["eval_run_id"]
    return payload


COMMANDS = ("status", *HANDLERS)


def run_command(
    command: str,
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    confirm: bool = False,
) -> dict[str, Any]:
    """Dispatch one ``$EXECUTION`` subcommand."""
    ctx = ExecutionContext.build(cycle_id, project_root, profile_id)
    if command == "status":
        return _status(command, ctx)
    handler = HANDLERS.get(command)
    if handler is None:
        return failure(command, "unknown_command", f"unknown command: {command}")
    if command in CONFIRM_COMMANDS and not confirm:
        return failure(command, "confirmation_required", f"{command} requires --confirm")
    blocked = require_working(command, ctx)
    if blocked:
        return blocked
    return handler(command, ctx)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Compose execution step control")
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    sub = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        sub_parser = sub.add_parser(command)
        if command in CONFIRM_COMMANDS:
            sub_parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    root, cycle_id = args.project_root.resolve(), args.cycle_id.strip()
    try:
        profile_id = resolve_profile_id(project_root=root, cycle_id=cycle_id)
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    session_dir = session_state_path(cycle_id, profile_id, root).parent
    try:
        with session_lock(session_dir, exclusive=False):
            result = run_command(
                args.command,
                cycle_id,
                root,
                profile_id=profile_id,
                confirm=bool(getattr(args, "confirm", False)),
            )
    except LockTimeoutError:
        result = failure(args.command, "lock_timeout", "session lock timeout")
    if result.get("ok") and "dispatch_input" in result:
        print(result["dispatch_input"])
        return 0
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(_cli())
