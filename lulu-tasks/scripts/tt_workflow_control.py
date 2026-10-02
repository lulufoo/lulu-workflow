#!/usr/bin/env python3
"""lulu-tasks workflow control. Session files are written only here.

CLI:
    tt_workflow_control.py --project-root . --cycle-id <id> resolve-context
    tt_workflow_control.py --project-root . --cycle-id <id> enter-evaluating
    tt_workflow_control.py --project-root . --cycle-id <id> apply-eval-disposition --disposition-json '<object>'
    tt_workflow_control.py --project-root . --cycle-id <id> put-task-list   # body on stdin
    tt_workflow_control.py --project-root . --cycle-id <id> put-task         # body on stdin
    tt_workflow_control.py --project-root . --cycle-id <id> deliver
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from tt_delivery_gate_schema import delivery_gate_file, write_delivery_gate
from tt_eval_runtime_schema import RUNTIME_FILENAME
from tt_session_schema import read_active_doc, session_file
from tt_task_list_schema import task_list_file, write_task_list
from tt_task_schema import write_task
from tt_workflow_common import detect_cycle_type, doc_dir
from tt_workflow_schema import read_workflow_state, transition_workflow, workflow_file

_UNIT = {
    "Drafting": "drafting",
    "Evaluating": "evaluating",
    "ReadyForDelivery": "delivery",
}


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _fail(message: str) -> int:
    return _emit({"ok": False, "error": message})


def _doc(project_root: Path, cycle_id: str) -> tuple[Path, Path, dict[str, str | int]]:
    active = read_active_doc(session_file(project_root, cycle_id))
    if active < 1:
        raise FileNotFoundError("lulu-tasks session is not started")
    doc = project_root / doc_dir(cycle_id, active)
    return doc, workflow_file(project_root, cycle_id, active), read_workflow_state(
        workflow_file(project_root, cycle_id, active)
    )


def _last_issues(doc: Path) -> list[Any]:
    path = doc / RUNTIME_FILENAME
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    issues = payload.get("last_issues") or []
    return issues if isinstance(issues, list) else []


def _task_paths(doc: Path) -> list[str]:
    root = doc / "tasks"
    if not root.is_dir():
        return []
    found = []
    for path in root.glob("t*/task.md"):
        if re.fullmatch(r"t[1-9]\d*", path.parent.name):
            found.append(path)
    found.sort(key=lambda path: int(path.parent.name[1:]))
    return [path.resolve().as_posix() for path in found]


def cmd_resolve_context(project_root: Path, cycle_id: str) -> int:
    try:
        doc, _state_path, state = _doc(project_root, cycle_id)
    except (FileNotFoundError, ValueError) as exc:
        return _fail(str(exc))
    current = str(state["current_state"])
    return _emit({
        "ok": True,
        "cycle_type": detect_cycle_type(cycle_id),
        "current_state": current,
        "evaluate_round": state["evaluate_round"],
        "tech_ref": state["tech_ref"],
        "last_issues": _last_issues(doc),
        "unit": _UNIT.get(current, ""),
    })


def cmd_enter_evaluating(project_root: Path, cycle_id: str) -> int:
    try:
        _doc_dir, state_path, state = _doc(project_root, cycle_id)
        nxt = transition_workflow(
            state_path,
            "Evaluating",
            evaluate_round=int(state["evaluate_round"]) + 1,
        )
    except (FileNotFoundError, ValueError) as exc:
        return _fail(str(exc))
    return _emit({
        "ok": True,
        "current_state": nxt["current_state"],
        "evaluate_round": nxt["evaluate_round"],
    })


def cmd_apply_eval_disposition(project_root: Path, cycle_id: str, payload: dict[str, Any]) -> int:
    if payload.get("ok") is not True:
        return _fail("eval disposition is not ok")
    disposition = str(payload.get("disposition") or "")
    try:
        _doc_dir, state_path, state = _doc(project_root, cycle_id)
        if state["current_state"] != "Evaluating":
            raise ValueError("apply-eval-disposition requires Evaluating")
        if disposition == "drafting":
            nxt = transition_workflow(state_path, "Drafting")
        elif disposition == "ready":
            nxt = transition_workflow(state_path, "ReadyForDelivery")
        else:
            return _fail(f"eval disposition {disposition!r} is not applied")
    except (FileNotFoundError, ValueError) as exc:
        return _fail(str(exc))
    return _emit({
        "ok": True,
        "disposition": disposition,
        "current_state": nxt["current_state"],
        "issues": payload.get("issues") or [],
    })


def cmd_put_task_list(project_root: Path, cycle_id: str, body: str) -> int:
    try:
        doc, _state_path, state = _doc(project_root, cycle_id)
        if state["current_state"] != "Drafting":
            raise ValueError("put-task-list requires Drafting")
        write_task_list(task_list_file(doc), body)
    except (FileNotFoundError, ValueError) as exc:
        return _fail(str(exc))
    return _emit({"ok": True, "current_state": "Drafting"})


def cmd_put_task(project_root: Path, cycle_id: str, body: str) -> int:
    try:
        doc, _state_path, state = _doc(project_root, cycle_id)
        if state["current_state"] != "Drafting":
            raise ValueError("put-task requires Drafting")
        path = write_task(doc, body)
    except (FileNotFoundError, ValueError) as exc:
        return _fail(str(exc))
    return _emit({"ok": True, "current_state": "Drafting", "task_path": path.resolve().as_posix()})


def cmd_deliver(project_root: Path, cycle_id: str) -> int:
    try:
        doc, state_path, state = _doc(project_root, cycle_id)
        if state["current_state"] != "ReadyForDelivery":
            raise ValueError("deliver requires ReadyForDelivery")
        paths = _task_paths(doc)
        write_delivery_gate(delivery_gate_file(doc), paths)
        nxt = transition_workflow(state_path, "Delivered")
    except (FileNotFoundError, ValueError) as exc:
        return _fail(str(exc))
    return _emit({
        "ok": True,
        "current_state": nxt["current_state"],
        "task_count": len(paths),
        "task_paths": paths,
    })


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="lulu-tasks workflow control.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--cycle-id", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("resolve-context")
    sub.add_parser("enter-evaluating")
    applied = sub.add_parser("apply-eval-disposition")
    applied.add_argument("--disposition-json", required=True)
    sub.add_parser("put-task-list")
    sub.add_parser("put-task")
    sub.add_parser("deliver")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.project_root).resolve()
    cycle_id = args.cycle_id.strip()
    if args.command == "resolve-context":
        return cmd_resolve_context(root, cycle_id)
    if args.command == "enter-evaluating":
        return cmd_enter_evaluating(root, cycle_id)
    if args.command == "apply-eval-disposition":
        try:
            payload = json.loads(args.disposition_json)
        except json.JSONDecodeError as exc:
            return _fail(f"disposition JSON is invalid: {exc}")
        if not isinstance(payload, dict):
            return _fail("disposition JSON must be an object")
        return cmd_apply_eval_disposition(root, cycle_id, payload)
    if args.command == "put-task-list":
        return cmd_put_task_list(root, cycle_id, sys.stdin.read())
    if args.command == "put-task":
        return cmd_put_task(root, cycle_id, sys.stdin.read())
    return cmd_deliver(root, cycle_id)


if __name__ == "__main__":
    raise SystemExit(main())
