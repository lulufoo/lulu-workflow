#!/usr/bin/env python3
"""Task-level control plane for lulu-code task-runner.

Subcommands:
    resolve-context   Build $CTX JSON for task-runner Step 0
    enter-phase       Append enter · {phase} to code-log.md
    run-tests         Run test_command; append test_run log; enforce red/green expectation
    commit-initial    git add -A, commit, write commit-ref, log
    commit-amend      Amend if worktree dirty; update commit-ref and log
    mark-done         Mark [x] in code-task-list and append enter · Done
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
from tc_run_test_suite import execute_test_command  # noqa: E402
def _load_ctx(cycle_dir: Path, task_id: str, project_root: Path) -> dict[str, Any]:
    return resolve_task_context(cycle_dir, task_id, project_root, include_model=False)


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


def resolve_context_cmd(cycle_dir: Path, task_id: str, project_root: Path) -> dict[str, Any]:
    return _load_ctx(cycle_dir, task_id, project_root)


def enter_phase_cmd(cycle_dir: Path, task_id: str, project_root: Path, phase: str) -> dict[str, Any]:
    ctx = _load_ctx(cycle_dir, task_id, project_root)
    append_enter(Path(ctx["task_output_dir"]), phase)
    return {"task_id": task_id, "phase": phase}


def run_tests_cmd(
    cycle_dir: Path,
    task_id: str,
    project_root: Path,
    expect: str,
) -> dict[str, Any]:
    if expect not in ("red", "green"):
        raise ValueError(f"expect must be red or green, got {expect!r}")

    ctx = _load_ctx(cycle_dir, task_id, project_root)
    worktree = Path(ctx["worktree_abs_path"])
    task_output_dir = Path(ctx["task_output_dir"])

    test_result = execute_test_command(
        project_root=project_root,
        worktree_path=worktree,
        test_command=ctx.get("test_command") or None,
    )
    append_test_run(
        task_output_dir,
        passed=test_result.passed,
        command=test_result.command,
        cwd=worktree,
        exit_code=test_result.exit_code,
        duration_ms=test_result.duration_ms,
        output=test_result.output,
    )

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


def commit_initial_cmd(cycle_dir: Path, task_id: str, project_root: Path) -> dict[str, Any]:
    ctx = _load_ctx(cycle_dir, task_id, project_root)
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


def commit_amend_cmd(cycle_dir: Path, task_id: str, project_root: Path) -> dict[str, Any]:
    ctx = _load_ctx(cycle_dir, task_id, project_root)
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


def mark_done_cmd(cycle_dir: Path, task_id: str, project_root: Path) -> dict[str, Any]:
    ctx = _load_ctx(cycle_dir, task_id, project_root)
    mark_task_done(Path(ctx["code_task_list_path"]), task_id)
    append_enter(Path(ctx["task_output_dir"]), "Done")
    return {"task_id": task_id, "marked_done": True}


def _cli() -> int:
    parser = argparse.ArgumentParser(description="lulu-code task control plane")
    parser.add_argument("--cycle-dir", required=True, help="Absolute path to cycle cache directory")
    parser.add_argument("--project-root", required=True, help="Absolute path to project root")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve-context", help="Build $CTX JSON for task-runner")
    resolve.add_argument("--task-id", required=True, help="Task id (e.g. t1)")

    enter = sub.add_parser("enter-phase", help="Append enter · phase to code-log.md")
    enter.add_argument("--task-id", required=True)
    enter.add_argument("--phase", required=True, help="Phase name (WriteTests, VerifyRed, ...)")

    tests = sub.add_parser("run-tests", help="Run tests with red/green expectation")
    tests.add_argument("--task-id", required=True)
    tests.add_argument("--expect", required=True, choices=["red", "green"])

    commit_init = sub.add_parser("commit-initial", help="Stage, commit, write commit-ref")
    commit_init.add_argument("--task-id", required=True)

    commit_amd = sub.add_parser("commit-amend", help="Amend commit if worktree dirty")
    commit_amd.add_argument("--task-id", required=True)

    done = sub.add_parser("mark-done", help="Mark task done in list and log Done phase")
    done.add_argument("--task-id", required=True)

    args = parser.parse_args()
    cycle_dir = Path(args.cycle_dir).resolve()
    project_root = Path(args.project_root).resolve()

    try:
        if args.command == "resolve-context":
            payload = resolve_context_cmd(cycle_dir, args.task_id, project_root)
        elif args.command == "enter-phase":
            payload = enter_phase_cmd(cycle_dir, args.task_id, project_root, args.phase)
        elif args.command == "run-tests":
            payload = run_tests_cmd(cycle_dir, args.task_id, project_root, args.expect)
        elif args.command == "commit-initial":
            payload = commit_initial_cmd(cycle_dir, args.task_id, project_root)
        elif args.command == "commit-amend":
            payload = commit_amend_cmd(cycle_dir, args.task_id, project_root)
        elif args.command == "mark-done":
            payload = mark_done_cmd(cycle_dir, args.task_id, project_root)
        else:
            parser.error(f"unknown command: {args.command}")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
