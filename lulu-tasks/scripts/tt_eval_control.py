#!/usr/bin/env python3
"""lulu-tasks Eval control — start a pass and route one full-remediation round.

One pass is one Eval round: every dimension probes in parallel, then Eval
remediates task chapters in place. The round is not re-probed.

CLI:
    python3 tt_eval_control.py --project-root . --cycle-id <id> begin-pass
    python3 tt_eval_control.py --project-root . --cycle-id <id> status
    python3 tt_eval_control.py --project-root . --cycle-id <id> route-remediation-result --result-json '<object>'

route-remediation-result input:
    a successful `remediation-complete` payload            -> disposition ready
    a failed `apply-remediation` payload whose reason starts
    with `tasks-scope-rejected`                             -> disposition drafting;
                                                               issues = pending Review rows
    anything else                                           -> {"ok": false, ...}

route-remediation-result stdout:
    {"ok": true, "disposition": "drafting" | "ready", "issues": [...]}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_EVAL_ADAPTER = _SCRIPTS / "eval"
_EVAL_SCRIPTS = _SCRIPTS.parents[1] / "eval" / "scripts"
for _path in (_SCRIPTS, _EVAL_ADAPTER, _EVAL_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from eval_path import ensure_eval_script_layers  # noqa: E402

ensure_eval_script_layers()

from review_io import parse_review_file  # noqa: E402
from tasks_eval_adapter import TasksEvalAdapter  # noqa: E402
from tasks_eval_target_publish import SCOPE_REJECTED  # noqa: E402
from tt_eval_runtime_schema import evaluate_dir, load_runtime, runtime_path  # noqa: E402

_REVIEW_GLOB = "tasks-review-e*.md"
_ISSUE_FIELDS = ("id", "root_cause", "location", "description")


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _emit_error(message: str) -> int:
    return _emit({"ok": False, "error": message})


def cmd_begin_pass(project_root: Path, cycle_id: str) -> int:
    adapter = TasksEvalAdapter()
    try:
        state = adapter.load_workflow_state(cycle_id, project_root)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))
    if state.get("current_state") != "Working":
        return _emit_error(
            "begin-pass requires workflow current_state Evaluating, "
            f"got {state.get('current_state')!r}"
        )
    session_dir = adapter.session_dir(cycle_id, project_root)
    runtime = load_runtime(runtime_path(session_dir))
    if runtime.get("focus_phase") == "evaluating":
        return _emit_error("begin-pass refused while a probe is in progress")
    runtime["last_outcome"] = ""
    runtime["last_disposition"] = ""
    runtime["last_issues"] = []
    runtime["pass_id"] = int(runtime.get("pass_id") or 0) + 1
    adapter.save_runtime(cycle_id, project_root, runtime)
    return _emit({"ok": True, "pass_id": runtime["pass_id"]})


def cmd_status(project_root: Path, cycle_id: str) -> int:
    adapter = TasksEvalAdapter()
    try:
        session_dir = adapter.session_dir(cycle_id, project_root)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))
    runtime = load_runtime(runtime_path(session_dir))
    return _emit({
        "ok": True,
        "focus_phase": runtime.get("focus_phase"),
        "pass_id": runtime.get("pass_id"),
        "last_disposition": runtime.get("last_disposition"),
        "last_issues": runtime.get("last_issues") or [],
    })


def _pending_review_issues(session_dir: Path, evaluate_round: int) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for review in sorted(evaluate_dir(session_dir, evaluate_round).glob(_REVIEW_GLOB)):
        for row in parse_review_file(review):
            if row.get("status", "").lower() != "pending":
                continue
            issue = {field: row.get(field, "") for field in _ISSUE_FIELDS}
            issue["review_path"] = review.resolve().as_posix()
            issues.append(issue)
    return issues


def _classify_result(result: dict[str, Any]) -> str | None:
    command = result.get("command")
    if result.get("ok") is True and command == "remediation-complete":
        return "ready"
    reason = str(result.get("reason") or result.get("error") or "")
    if result.get("ok") is False and command == "apply-remediation" and reason.startswith(SCOPE_REJECTED):
        return "drafting"
    return None


def cmd_route_remediation_result(
    project_root: Path,
    cycle_id: str,
    *,
    result: dict[str, Any],
) -> int:
    disposition = _classify_result(result)
    if disposition is None:
        return _emit_error(
            "result must be a successful remediation-complete payload or an "
            f"apply-remediation failure whose reason starts with {SCOPE_REJECTED!r}"
        )
    adapter = TasksEvalAdapter()
    try:
        session_dir = adapter.session_dir(cycle_id, project_root)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))
    runtime = load_runtime(runtime_path(session_dir))
    if runtime.get("focus_phase") != "evaluating":
        return _emit_error("route-remediation-result requires focus_phase=evaluating")
    issues: list[dict[str, Any]] = []
    if disposition == "drafting":
        try:
            issues = _pending_review_issues(session_dir, int(runtime.get("evaluate_round") or 0))
        except (OSError, ValueError) as exc:
            return _emit_error(f"cannot read Review files: {exc}")
        issues.insert(0, {
            "id": "scope",
            "root_cause": "WO-ERROR",
            "location": "task-list.md",
            "description": str(result.get("reason") or result.get("error") or SCOPE_REJECTED),
        })
    try:
        adapter.finalize_eval_outcome(
            cycle_id,
            project_root,
            outcome="pass" if disposition == "ready" else "fail",
            issues=issues,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        return _emit_error(str(exc))
    runtime = load_runtime(runtime_path(session_dir))
    runtime["last_disposition"] = disposition
    runtime["last_issues"] = issues
    adapter.save_runtime(cycle_id, project_root, runtime)
    return _emit({"ok": True, "disposition": disposition, "issues": issues})


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="lulu-tasks Eval control.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--cycle-id", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("begin-pass")
    sub.add_parser("status")
    route = sub.add_parser("route-remediation-result")
    route.add_argument("--result-json", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    if args.command == "begin-pass":
        return cmd_begin_pass(project_root, cycle_id)
    if args.command == "status":
        return cmd_status(project_root, cycle_id)
    if args.command == "route-remediation-result":
        try:
            result = json.loads(args.result_json)
        except json.JSONDecodeError as exc:
            return _emit_error(f"invalid --result-json: {exc}")
        if not isinstance(result, dict):
            return _emit_error("--result-json must be a JSON object")
        return cmd_route_remediation_result(project_root, cycle_id, result=result)
    return _emit_error(f"unknown command: {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
