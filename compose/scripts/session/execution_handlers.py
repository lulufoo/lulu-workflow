#!/usr/bin/env python3
"""Step command handlers for ``$EXECUTION`` (one function per subcommand)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

import execution_checks as checks  # noqa: E402
from compose_session import document_file_path  # noqa: E402
from compose_writing_control import validate_writing_artifacts  # noqa: E402
from execution_context import (  # noqa: E402
    ExecutionContext,
    current_state,
    failure,
    mutate,
    success,
)
from execution_state_schema import load_execution_state  # noqa: E402
from execution_transitions import IllegalTransitionError, apply_step  # noqa: E402

CONFIRM_COMMANDS = ("accept", "fix", "re-evaluate", "reopen")
_REVERSE_INIT = {"reverse-to-inductive": True, "reverse-to-deductive": False}
Handler = Callable[[str, ExecutionContext], dict[str, Any]]


def _with_dispatch(payload: dict[str, Any], build: Callable[[], str]) -> dict[str, Any]:
    if payload.get("ok"):
        try:
            payload["dispatch_input"] = build()
        except (OSError, ValueError) as exc:
            payload["dispatch_input_error"] = str(exc)
    return payload


def _complete(
    command: str,
    ctx: ExecutionContext,
    *,
    expected: str,
    stamp: str,
    check: Callable[[], str | None],
    code: str,
    flag: str,
) -> dict[str, Any]:
    state = current_state(command, ctx, expected)
    if isinstance(state, dict):
        return state
    err = check()
    if err:
        return failure(command, code, err)
    checks.write_stamp(ctx.execution_dir, stamp)
    return success(command, state=state, **{flag: True})


def _require_stamp(ctx: ExecutionContext, stamp: str, message: str) -> None:
    if not checks.has_stamp(ctx.execution_dir, stamp):
        raise IllegalTransitionError("illegal_transition", message)


def _plain(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    return mutate(command, ctx, lambda s: apply_step(s, command))


def _enter_fact_intake(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    return _with_dispatch(_plain(command, ctx), lambda: ctx.fact_intake_dispatch())


def _complete_fact_intake(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    return _complete(
        command,
        ctx,
        expected="FactIntake",
        stamp=checks.FACT_INTAKE_STAMP,
        check=lambda: checks.fact_intake_complete_error(
            ctx.execution_dir, inductive=ctx.inductive
        ),
        code="fact_intake_incomplete",
        flag="fact_intake_complete",
    )


def _enter_inductive(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    if not ctx.inductive:
        return failure(command, "illegal_transition", "enter-inductive requires pipeline.inductive")

    def apply(state: dict[str, Any]) -> dict[str, Any]:
        _require_stamp(
            ctx, checks.FACT_INTAKE_STAMP, "enter-inductive requires completed fact intake"
        )
        new = apply_step(state, command)
        checks.strip_derived(ctx.execution_dir)
        return new

    payload = mutate(command, ctx, apply)
    if payload.get("ok"):
        try:
            checks.init_inductive_bundle(ctx.execution_dir, ctx.cycle_id, ctx.profile_id)
        except (OSError, ValueError) as exc:
            return failure(command, "illegal_transition", str(exc))
    return _with_dispatch(payload, lambda: ctx.producer_dispatch(inductive=True))


def _complete_inductive(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    return _complete(
        command,
        ctx,
        expected="Inductive",
        stamp=checks.INDUCTIVE_STAMP,
        check=lambda: checks.inductive_complete_error(ctx.execution_dir),
        code="inductive_incomplete",
        flag="inductive_complete",
    )


def _enter_deductive(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    def apply(state: dict[str, Any]) -> dict[str, Any]:
        _require_stamp(
            ctx, checks.FACT_INTAKE_STAMP, "enter-deductive requires completed fact intake"
        )
        current = str(state["state"])
        if current == "FactIntake" and ctx.inductive:
            raise IllegalTransitionError(
                "illegal_transition",
                "enter-deductive from FactIntake requires pipeline.inductive=false",
            )
        if current == "Inductive":
            if not ctx.inductive:
                raise IllegalTransitionError(
                    "illegal_transition",
                    "enter-deductive from Inductive requires pipeline.inductive",
                )
            if checks.inductive_complete_error(ctx.execution_dir) is not None:
                raise IllegalTransitionError(
                    "illegal_transition", "enter-deductive requires completed inductive"
                )
        new = apply_step(state, command)
        checks.strip_derived(ctx.execution_dir)
        return new

    payload = mutate(command, ctx, apply)
    return _with_dispatch(payload, lambda: ctx.producer_dispatch(inductive=False))


def _complete_deductive(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    return _complete(
        command,
        ctx,
        expected="Deductive",
        stamp=checks.DEDUCTIVE_STAMP,
        check=lambda: checks.deductive_complete_error(ctx.revision_dir, ctx.execution_dir),
        code="deductive_incomplete",
        flag="deductive_complete",
    )


def _enter_writing(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    err = checks.deductive_complete_error(ctx.revision_dir, ctx.execution_dir)
    if err:
        return failure(command, "deductive_incomplete", err)
    checks.write_stamp(ctx.execution_dir, checks.DEDUCTIVE_STAMP)
    return _with_dispatch(_plain(command, ctx), ctx.writing_dispatch)


def _complete_writing(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    return _complete(
        command,
        ctx,
        expected="Writing",
        stamp=checks.WRITING_STAMP,
        check=lambda: validate_writing_artifacts(
            ctx.revision_dir,
            document_file_path(ctx.cycle_id, ctx.project_root, ctx.profile_id),
            ctx.project_root,
            ctx.profile_id,
        ),
        code="writing_incomplete",
        flag="writing_complete",
    )


def _enter_freeedit(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    if not ctx.freeedit:
        return failure(command, "illegal_transition", "enter-freeedit requires pipeline.freeedit")
    if not checks.has_stamp(ctx.execution_dir, checks.WRITING_STAMP):
        return failure(command, "writing_incomplete", "writing complete check failed")
    return _plain(command, ctx)


def _reverse(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    init_inductive = _REVERSE_INIT.get(command)
    if init_inductive is True and not ctx.inductive:
        return failure(command, "illegal_transition", f"{command} requires pipeline.inductive")

    def apply(state: dict[str, Any]) -> dict[str, Any]:
        new = apply_step(state, command)
        if init_inductive is None:
            checks.clear_stamp(ctx.execution_dir, checks.WRITING_STAMP)
        else:
            checks.reset_stage_complete(
                ctx.execution_dir,
                cycle_id=ctx.cycle_id,
                profile_id=ctx.profile_id,
                init_inductive=init_inductive,
            )
            checks.strip_derived(ctx.execution_dir)
        return new

    payload = mutate(command, ctx, apply)
    if init_inductive is None:
        return _with_dispatch(payload, ctx.writing_dispatch)
    return _with_dispatch(payload, lambda: ctx.producer_dispatch(inductive=init_inductive))


def _enter_evaluating(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    run_id: dict[str, str] = {}

    def apply(state: dict[str, Any]) -> dict[str, Any]:
        if state["state"] == "Writing" and not checks.has_stamp(
            ctx.execution_dir, checks.WRITING_STAMP
        ):
            raise IllegalTransitionError("writing_incomplete", "writing complete check failed")
        new = apply_step(state, command)
        run_id["eval_run_id"] = checks.write_eval_run(ctx.execution_dir, new)
        return new

    payload = mutate(command, ctx, apply)
    if payload.get("ok"):
        payload["eval_run_id"] = run_id["eval_run_id"]
    return payload


def _eval_exit(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    def apply(state: dict[str, Any]) -> dict[str, Any]:
        err = checks.eval_run_is_current(ctx.execution_dir, state)
        if err:
            raise IllegalTransitionError("stale_eval", err)
        return apply_step(state, command)

    return mutate(command, ctx, apply)


def _re_evaluate(command: str, ctx: ExecutionContext) -> dict[str, Any]:
    state = current_state(command, ctx, "Evaluating")
    if isinstance(state, dict):
        return state
    run_id = checks.write_eval_run(ctx.execution_dir, load_execution_state(ctx.revision_dir))
    return success(command, state=state, eval_run_id=run_id)


HANDLERS: dict[str, Handler] = {
    "enter-fact-intake": _enter_fact_intake,
    "complete-fact-intake": _complete_fact_intake,
    "enter-inductive": _enter_inductive,
    "complete-inductive": _complete_inductive,
    "enter-deductive": _enter_deductive,
    "complete-deductive": _complete_deductive,
    "enter-writing": _enter_writing,
    "complete-writing": _complete_writing,
    "enter-freeedit": _enter_freeedit,
    "reverse-to-inductive": _reverse,
    "reverse-to-deductive": _reverse,
    "reverse-to-writing": _reverse,
    "enter-evaluating": _enter_evaluating,
    "accept": _eval_exit,
    "fix": _eval_exit,
    "re-evaluate": _re_evaluate,
    "reopen": _plain,
}
