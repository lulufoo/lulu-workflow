#!/usr/bin/env python3
"""Task-level control plane for lulu-exec task-runner.

Subcommands:
    resolve-context   Build $CTX JSON for task-runner Step 0
    enter-phase       Append enter · {phase} to code-log.md
    run-tests         Run the checkout test command; empty command skips; else enforce red/green
    commit-initial    git add -A, commit, write commit-ref, log
    commit-amend      Amend if worktree dirty; update commit-ref and log
    mark-done         Mark [x] in code-task-list and append enter · Done
    record-receipt    Write action-receipt.json for an action task (results JSON on stdin)

Every subcommand accepts --conversation-id (auto-injected by hook_guard on Cursor)
and enforces subagent dispatch before loading $CTX: if the caller's conversation_id
matches the session's master_conversation_id (the orchestrating parent conversation
recorded at Starting), the command aborts with "SUBAGENT_REQUIRED: ..." (exit code 1,
message on stderr) instead of running inline.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tc_code_log import append_enter, append_git_commit, append_test_run  # noqa: E402
from tc_code_task_list import mark_task_done, parse_task_title  # noqa: E402
from tc_commit_message import render_commit_message  # noqa: E402
from tc_commit_ref_schema import load_commit_ref, write_commit_ref  # noqa: E402
from tc_git_ops import git_add_all, git_commit, git_commit_amend, git_head_sha, status_clean  # noqa: E402
from tc_resolve_task_context import resolve_task_context  # noqa: E402
from tc_action_receipt_schema import save_receipt, receipt_path  # noqa: E402
from tc_run_test_suite import execute_test_command  # noqa: E402
from tc_workflow_state_schema import load_workflow_state, resolve_workflow_state_path  # noqa: E402

_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
from active_context_schema import resolve_conversation_id  # noqa: E402
from cycle_log_schema import append_cycle_log  # noqa: E402
from platform_schema import detect_platform  # noqa: E402

from tc_workflow_common import EXEC_STAGE  # noqa: E402

_SUBAGENT_REQUIRED_PREFIX = "SUBAGENT_REQUIRED:"
_STAGE = EXEC_STAGE


def _check_subagent_dispatch(cycle_dir: Path, task_id: str, conversation_id: str) -> None:
    """Reject any subcommand invoked from the orchestrating parent conversation."""
    if detect_platform() != "cursor":
        return

    conv_id = resolve_conversation_id(conversation_id)
    if not conv_id:
        return

    ws_path = resolve_workflow_state_path(cycle_dir)
    state = load_workflow_state(ws_path)
    master = state.get("master_conversation_id", "").strip()
    if not master:
        return

    if master != conv_id:
        return

    append_cycle_log(
        cycle_dir,
        level="ERROR",
        stage=_STAGE,
        message=(
            f"task {task_id}: command blocked — invoked from orchestrating conversation, "
            f"no subagent dispatch detected (conversation_id={conv_id})"
        ),
    )

    raise ValueError(
        f"{_SUBAGENT_REQUIRED_PREFIX} this command was invoked from the orchestrating "
        "conversation itself (conversation_id matches Starting's master_conversation_id). "
        "lulu-exec/SKILL.md requires every task to run inside a dispatched "
        "kind runner via $SUBAGENT_TOOL (Task, run_in_background: false). "
        "Do not execute the task inline. Dispatch a subagent for this task "
        "and retry."
    )


def _load_ctx(
    cycle_dir: Path,
    task_id: str,
    project_root: Path,
    *,
    conversation_id: str = "",
) -> dict[str, Any]:
    _check_subagent_dispatch(cycle_dir, task_id, conversation_id)
    return resolve_task_context(cycle_dir, task_id, project_root)


def _commit_summary(ctx: dict[str, Any]) -> str:
    task_id = ctx["task_id"]
    list_path = Path(ctx["code_task_list_path"])
    if list_path.exists():
        title = parse_task_title(list_path.read_text(encoding="utf-8"), task_id)
        if title:
            return title

    task_path = Path(ctx["work_order_task_path"])
    if task_path.exists():
        content = task_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return task_id


def resolve_context_cmd(
    cycle_dir: Path,
    task_id: str,
    project_root: Path,
    *,
    conversation_id: str = "",
) -> dict[str, Any]:
    ctx = _load_ctx(cycle_dir, task_id, project_root, conversation_id=conversation_id)
    ctx.pop("checkout_name", None)
    return ctx


def enter_phase_cmd(
    cycle_dir: Path,
    task_id: str,
    project_root: Path,
    phase: str,
    *,
    conversation_id: str = "",
) -> dict[str, Any]:
    ctx = _load_ctx(cycle_dir, task_id, project_root, conversation_id=conversation_id)
    append_enter(Path(ctx["task_output_dir"]), phase)
    return {"task_id": task_id, "phase": phase}


def run_tests_cmd(
    cycle_dir: Path,
    task_id: str,
    project_root: Path,
    expect: str,
    *,
    conversation_id: str = "",
) -> dict[str, Any]:
    if expect not in ("red", "green"):
        raise ValueError(f"expect must be red or green, got {expect!r}")

    ctx = _load_ctx(cycle_dir, task_id, project_root, conversation_id=conversation_id)
    worktree = Path(ctx["worktree_abs_path"])
    task_output_dir = Path(ctx["task_output_dir"])
    command = (ctx.get("test_command") or "").strip()
    test_result = execute_test_command(
        project_root=project_root,
        worktree_path=worktree,
        test_command=command or None,
        checkout_name=str(ctx.get("checkout_name") or ""),
    )
    append_test_run(
        task_output_dir,
        passed=test_result.passed,
        command=test_result.command,
        cwd=worktree,
        exit_code=test_result.exit_code,
        duration_ms=test_result.duration_ms,
        output=test_result.output,
        skipped=getattr(test_result, "skipped", False),
    )

    if getattr(test_result, "skipped", False):
        return {
            "task_id": task_id,
            "expect": expect,
            "passed": True,
            "exit_code": 0,
            "skipped": True,
        }

    if expect == "red" and test_result.passed:
        raise ValueError("VerifyRed: all tests passed unexpectedly")
    if expect == "green" and not test_result.passed:
        raise ValueError(f"tests failed: exit_code={test_result.exit_code}")

    return {
        "task_id": task_id,
        "expect": expect,
        "passed": test_result.passed,
        "exit_code": test_result.exit_code,
    }


def commit_initial_cmd(
    cycle_dir: Path,
    task_id: str,
    project_root: Path,
    *,
    conversation_id: str = "",
) -> dict[str, Any]:
    ctx = _load_ctx(cycle_dir, task_id, project_root, conversation_id=conversation_id)
    worktree = ctx["worktree_abs_path"]
    task_output_dir = Path(ctx["task_output_dir"])

    git_add_all(worktree)
    summary = _commit_summary(ctx)
    message = render_commit_message(
        ctx["commit_message_template"],
        task_id=task_id,
        summary=summary,
    )
    initial_commit = git_commit(worktree, message)

    recorded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ref_path = task_output_dir / "commit-ref.md"
    write_commit_ref(
        ref_path,
        {
            "task_id": task_id,
            "branch": ctx["branch"],
            "initial_commit": initial_commit,
            "final_commit": initial_commit,
            "commit_message": message,
            "amended": False,
            "recorded_at": recorded_at,
        },
    )
    append_git_commit(task_output_dir, kind="initial", sha=initial_commit, message=message)

    return {
        "task_id": task_id,
        "initial_commit": initial_commit,
        "final_commit": initial_commit,
        "commit_message": message,
    }


def commit_amend_cmd(
    cycle_dir: Path,
    task_id: str,
    project_root: Path,
    *,
    conversation_id: str = "",
) -> dict[str, Any]:
    ctx = _load_ctx(cycle_dir, task_id, project_root, conversation_id=conversation_id)
    worktree = ctx["worktree_abs_path"]
    task_output_dir = Path(ctx["task_output_dir"])
    ref_path = task_output_dir / "commit-ref.md"

    if status_clean(worktree):
        data = load_commit_ref(ref_path)
        return {
            "task_id": task_id,
            "skipped": True,
            "final_commit": data["final_commit"],
        }

    data = load_commit_ref(ref_path)
    final_commit = git_commit_amend(worktree)
    message = data["commit_message"]
    recorded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    write_commit_ref(
        ref_path,
        {
            "task_id": task_id,
            "branch": ctx["branch"],
            "initial_commit": data["initial_commit"],
            "final_commit": final_commit,
            "commit_message": message,
            "amended": True,
            "recorded_at": recorded_at,
        },
    )
    append_git_commit(task_output_dir, kind="amend", sha=final_commit, message=message)

    return {
        "task_id": task_id,
        "skipped": False,
        "amended": True,
        "final_commit": final_commit,
    }


def _parse_results(raw: str) -> list[Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"record-receipt stdin is not JSON: {exc}") from exc
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    if not isinstance(data, list):
        raise ValueError("record-receipt stdin must be a list of results")
    return data


def record_receipt_cmd(
    cycle_dir: Path,
    task_id: str,
    project_root: Path,
    *,
    results: list[Any],
    conversation_id: str = "",
) -> dict[str, Any]:
    ctx = _load_ctx(cycle_dir, task_id, project_root, conversation_id=conversation_id)
    if ctx.get("kind") != "action":
        raise ValueError(f"record-receipt is for action tasks, got kind {ctx.get('kind')!r}")
    session_dir = Path(ctx["task_output_dir"]).parent.parent
    save_receipt(
        receipt_path(session_dir, task_id),
        {
            "version": 2,
            "task_id": task_id,
            "goal": ctx["goal"],
            "effects": ctx["effects"],
            "results": results,
        },
        ctx["acceptance"],
    )
    return {"task_id": task_id, "criteria": len(ctx["acceptance"]), "ok": True}


def mark_done_cmd(
    cycle_dir: Path,
    task_id: str,
    project_root: Path,
    *,
    conversation_id: str = "",
) -> dict[str, Any]:
    ctx = _load_ctx(cycle_dir, task_id, project_root, conversation_id=conversation_id)
    mark_task_done(Path(ctx["code_task_list_path"]), task_id)
    append_enter(Path(ctx["task_output_dir"]), "Done")
    return {"task_id": task_id, "marked_done": True}


def _cli() -> int:
    # hook_guard appends --conversation-id to the *end* of the shell command, i.e. after
    # the subcommand and its own args — so the flag must be registered on every subparser
    # too, not just the top-level parser. A shared, no-help parent avoids repeating it 6x.
    conv_id_parent = argparse.ArgumentParser(add_help=False)
    conv_id_parent.add_argument(
        "--conversation-id",
        default="",
        help="Injected by hook_guard; current caller conversation id.",
    )

    parser = argparse.ArgumentParser(description="lulu-exec task control plane", parents=[conv_id_parent])
    parser.add_argument("--cycle-dir", required=True, help="Absolute path to cycle cache directory")
    parser.add_argument("--project-root", required=True, help="Absolute path to project root")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve-context", help="Build $CTX JSON for task-runner", parents=[conv_id_parent])
    resolve.add_argument("--task-id", required=True, help="Task id (e.g. t1)")

    enter = sub.add_parser("enter-phase", help="Append enter · phase to code-log.md", parents=[conv_id_parent])
    enter.add_argument("--task-id", required=True)
    enter.add_argument("--phase", required=True, help="Phase name (WriteTests, VerifyRed, ...)")

    tests = sub.add_parser("run-tests", help="Run tests with red/green expectation", parents=[conv_id_parent])
    tests.add_argument("--task-id", required=True)
    tests.add_argument("--expect", required=True, choices=["red", "green"])

    commit_init = sub.add_parser("commit-initial", help="Stage, commit, write commit-ref", parents=[conv_id_parent])
    commit_init.add_argument("--task-id", required=True)

    commit_amd = sub.add_parser("commit-amend", help="Amend commit if worktree dirty", parents=[conv_id_parent])
    commit_amd.add_argument("--task-id", required=True)

    done = sub.add_parser("mark-done", help="Mark task done in list and log Done phase", parents=[conv_id_parent])
    done.add_argument("--task-id", required=True)

    receipt = sub.add_parser(
        "record-receipt",
        help="Write action receipt; stdin is a JSON list of {criterion, evidence, met}",
        parents=[conv_id_parent],
    )
    receipt.add_argument("--task-id", required=True)

    args = parser.parse_args()
    cycle_dir = Path(args.cycle_dir).resolve()
    project_root = Path(args.project_root).resolve()

    try:
        if args.command == "resolve-context":
            payload = resolve_context_cmd(
                cycle_dir,
                args.task_id,
                project_root,
                conversation_id=args.conversation_id,
            )
        elif args.command == "enter-phase":
            payload = enter_phase_cmd(
                cycle_dir,
                args.task_id,
                project_root,
                args.phase,
                conversation_id=args.conversation_id,
            )
        elif args.command == "run-tests":
            payload = run_tests_cmd(
                cycle_dir,
                args.task_id,
                project_root,
                args.expect,
                conversation_id=args.conversation_id,
            )
        elif args.command == "commit-initial":
            payload = commit_initial_cmd(
                cycle_dir,
                args.task_id,
                project_root,
                conversation_id=args.conversation_id,
            )
        elif args.command == "commit-amend":
            payload = commit_amend_cmd(
                cycle_dir,
                args.task_id,
                project_root,
                conversation_id=args.conversation_id,
            )
        elif args.command == "mark-done":
            payload = mark_done_cmd(
                cycle_dir,
                args.task_id,
                project_root,
                conversation_id=args.conversation_id,
            )
        elif args.command == "record-receipt":
            payload = record_receipt_cmd(
                cycle_dir,
                args.task_id,
                project_root,
                results=_parse_results(sys.stdin.read()),
                conversation_id=args.conversation_id,
            )
        else:
            parser.error(f"unknown command: {args.command}")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
