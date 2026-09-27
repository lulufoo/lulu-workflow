#!/usr/bin/env python3
"""lulu-tasks Eval control — start a pass and route one probe-only result.

CLI:
    python3 tt_eval_control.py --project-root . --cycle-id <id> begin-pass
    python3 tt_eval_control.py --project-root . --cycle-id <id> status
    python3 tt_eval_control.py --project-root . --cycle-id <id> route-probe-result --probe-result-json '<object>'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_EVAL_ADAPTER = _SCRIPTS / "eval"
for _path in (_SCRIPTS, _EVAL_ADAPTER):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from tasks_eval_adapter import TasksEvalAdapter  # noqa: E402
from tt_eval_runtime_schema import (  # noqa: E402
    PHASES,
    load_runtime,
    next_phase,
    runtime_path,
)

_FORBIDDEN_ROOT_CAUSES = frozenset({
    "SOT-DEFECT",
    "UNRESOLVABLE",
    "DECISION-REQUIRED",
})


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _emit_error(message: str) -> int:
    return _emit({"ok": False, "error": message})


def _root_cause(issue: dict[str, Any]) -> str:
    return str(issue.get("root_cause") or "").strip().upper()


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
    runtime["phase"] = PHASES[0]
    runtime["probing_phase"] = ""
    runtime["last_outcome"] = ""
    runtime["last_disposition"] = ""
    runtime["last_issues"] = []
    runtime["pass_id"] = int(runtime.get("pass_id") or 0) + 1
    adapter.save_runtime(cycle_id, project_root, runtime)
    return _emit({
        "ok": True,
        "phase": PHASES[0],
        "pass_id": runtime["pass_id"],
    })


def cmd_status(project_root: Path, cycle_id: str) -> int:
    adapter = TasksEvalAdapter()
    try:
        session_dir = adapter.session_dir(cycle_id, project_root)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))
    runtime = load_runtime(runtime_path(session_dir))
    return _emit({
        "ok": True,
        "phase": runtime.get("phase"),
        "probing_phase": runtime.get("probing_phase"),
        "focus_phase": runtime.get("focus_phase"),
        "pass_id": runtime.get("pass_id"),
        "last_disposition": runtime.get("last_disposition"),
        "last_issues": runtime.get("last_issues") or [],
    })


def cmd_route_probe_result(
    project_root: Path,
    cycle_id: str,
    *,
    probe_result: dict[str, Any],
) -> int:
    if probe_result.get("ok") is not True or probe_result.get("command") != "complete-probe-only":
        return _emit_error("probe result must be a successful complete-probe-only payload")
    issues = probe_result.get("issues")
    if not isinstance(issues, list) or any(not isinstance(issue, dict) for issue in issues):
        return _emit_error("probe result issues must be an array of objects")
    adapter = TasksEvalAdapter()
    try:
        session_dir = adapter.session_dir(cycle_id, project_root)
    except (FileNotFoundError, ValueError) as exc:
        return _emit_error(str(exc))
    runtime = load_runtime(runtime_path(session_dir))
    if runtime.get("focus_phase") != "evaluating":
        return _emit_error("route-probe-result requires focus_phase=evaluating")
    phase = str(runtime.get("probing_phase") or "")
    if phase not in PHASES:
        return _emit_error(f"probe phase is {phase!r}")
    forbidden = [issue for issue in issues if _root_cause(issue) in _FORBIDDEN_ROOT_CAUSES]
    outcome = "fail" if issues else "pass"
    try:
        adapter.finalize_eval_outcome(cycle_id, project_root, outcome=outcome, issues=list(issues))
    except (FileNotFoundError, ValueError, OSError) as exc:
        return _emit_error(str(exc))
    runtime = load_runtime(runtime_path(session_dir))
    if forbidden:
        runtime["last_disposition"] = "rejected"
        runtime["last_issues"] = list(issues)
        runtime["phase"] = PHASES[0]
        adapter.save_runtime(cycle_id, project_root, runtime)
        return _emit_error(
            "probe emitted a SoT root cause; lulu-tasks eval does not handle it"
        )
    if issues:
        runtime["phase"] = PHASES[0]
        runtime["last_disposition"] = "drafting"
        runtime["last_issues"] = list(issues)
        adapter.save_runtime(cycle_id, project_root, runtime)
        return _emit({
            "ok": True,
            "disposition": "drafting",
            "phase": phase,
            "next_phase": "",
            "issues": issues,
        })
    following = next_phase(phase)
    if following is None:
        runtime["last_disposition"] = "ready"
        runtime["last_issues"] = []
        adapter.save_runtime(cycle_id, project_root, runtime)
        return _emit({
            "ok": True,
            "disposition": "ready",
            "phase": phase,
            "next_phase": "",
            "issues": [],
        })
    runtime["phase"] = following
    runtime["last_disposition"] = "continue"
    runtime["last_issues"] = []
    adapter.save_runtime(cycle_id, project_root, runtime)
    return _emit({
        "ok": True,
        "disposition": "continue",
        "phase": phase,
        "next_phase": following,
        "issues": [],
    })


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="lulu-tasks Eval control.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--cycle-id", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("begin-pass")
    sub.add_parser("status")
    route = sub.add_parser("route-probe-result")
    route.add_argument("--probe-result-json", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    project_root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    if args.command == "begin-pass":
        return cmd_begin_pass(project_root, cycle_id)
    if args.command == "status":
        return cmd_status(project_root, cycle_id)
    if args.command == "route-probe-result":
        try:
            probe_result = json.loads(args.probe_result_json)
        except json.JSONDecodeError as exc:
            return _emit_error(f"invalid --probe-result-json: {exc}")
        if not isinstance(probe_result, dict):
            return _emit_error("--probe-result-json must be a JSON object")
        return cmd_route_probe_result(project_root, cycle_id, probe_result=probe_result)
    return _emit_error(f"unknown command: {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
