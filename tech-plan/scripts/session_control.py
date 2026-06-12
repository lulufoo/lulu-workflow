#!/usr/bin/env python3
"""Session control for tech-plan orchestrator.

Subcommands:
    start-evaluating     Drafting -> Evaluating (+ evaluate-state.md init)
    ready-for-delivery   Drafting|Evaluating -> ReadyForDelivery
    deliver              ReadyForDelivery -> Delivered (+ human-delivery-gate.md)
    abandon-evaluation   Evaluating -> Drafting (requires evaluate-state abandoned)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_control import init_round  # noqa: E402
from evaluate_state_schema import (  # noqa: E402
    load_evaluate_state,
    resolve_evaluate_state_path_from_cycle,
)
from human_delivery_gate_schema import write_approved  # noqa: E402
from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import approval_path  # noqa: E402
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
    save_workflow_state,
)

_CMD_START_EVALUATING = "start-evaluating"
_CMD_READY = "ready-for-delivery"
_CMD_DELIVER = "deliver"
_CMD_ABANDON = "abandon-evaluation"
_EXPECTED_DELIVER_STATE = "ReadyForDelivery"
_EXPECTED_ABANDON_STATE = "Evaluating"


def _gate_path(cycle_id: str, project_root: Path) -> Path:
    return project_root / approval_path(
        cycle_id,
        load_active_doc_from_cycle(cycle_id, project_root),
    )


def _success(command: str, current_state: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "command": command,
        "current_state": current_state,
    }
    payload.update(extra)
    return payload


def _failure(command: str, current_state: str) -> dict[str, Any]:
    return {
        "ok": False,
        "command": command,
        "current_state": current_state,
        "resume": _build_resume(command, current_state),
    }


def _failure_deliver(current_state: str) -> dict[str, Any]:
    return {
        "ok": False,
        "command": _CMD_DELIVER,
        "current_state": current_state,
        "message": (
            f"deliver 被拒绝：当前状态为 {current_state}，"
            f"预期状态为 {_EXPECTED_DELIVER_STATE}。请暂停执行，等待用户指示。"
        ),
    }


def _failure_abandon(current_state: str, message: str) -> dict[str, Any]:
    return {
        "ok": False,
        "command": _CMD_ABANDON,
        "current_state": current_state,
        "message": message,
    }


def _build_resume(command: str, current_state: str) -> dict[str, Any]:
    if current_state == "Invalidated":
        return {
            "entry": None,
            "action": "当前会话已 Invalidated。",
        }
    if current_state == "Delivered":
        if command == _CMD_DELIVER:
            action = "当前状态是 Delivered，无需 deliver。"
        else:
            action = "当前状态是 Delivered，无需 ready-for-delivery。"
        return {"entry": "Delivered", "action": action}
    return {
        "entry": current_state,
        "action": f"当前状态是 {current_state}，请先执行完 {current_state}。",
    }


def start_evaluating(cycle_id: str, project_root: Path) -> dict[str, Any]:
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current == "Evaluating":
        try:
            evaluate_round = int(state.get("evaluate_round", "0"))
        except ValueError:
            evaluate_round = 0
        return _success(
            _CMD_START_EVALUATING,
            "Evaluating",
            evaluate_round=evaluate_round,
        )

    if current != "Drafting":
        return _failure(_CMD_START_EVALUATING, current)

    try:
        evaluate_round = int(state.get("evaluate_round", "0")) + 1
    except ValueError:
        evaluate_round = 1

    merged = dict(state)
    merged.pop("skip_evaluate_requested", None)
    merged["current_state"] = "Evaluating"
    merged["evaluate_round"] = str(evaluate_round)
    save_workflow_state(ws_path, merged, merge=False)

    init_round(cycle_id, project_root, mode=merged["mode"])

    return _success(
        _CMD_START_EVALUATING,
        "Evaluating",
        evaluate_round=evaluate_round,
    )


def ready_for_delivery(cycle_id: str, project_root: Path) -> dict[str, Any]:
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current == "ReadyForDelivery":
        return _success(_CMD_READY, "ReadyForDelivery")

    if current == "Drafting":
        updates: dict[str, str] = {"current_state": "ReadyForDelivery"}
        updates["skip_evaluate_requested"] = "true"
        save_workflow_state(ws_path, updates)
        return _success(_CMD_READY, "ReadyForDelivery")

    if current == "Evaluating":
        merged = dict(state)
        merged.pop("skip_evaluate_requested", None)
        merged["current_state"] = "ReadyForDelivery"
        save_workflow_state(ws_path, merged, merge=False)
        return _success(_CMD_READY, "ReadyForDelivery")

    return _failure(_CMD_READY, current)


def deliver(cycle_id: str, project_root: Path, *, note: str = "") -> dict[str, Any]:
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current != _EXPECTED_DELIVER_STATE:
        return _failure_deliver(current)

    write_approved(_gate_path(cycle_id, project_root), note=note)

    merged = dict(state)
    merged.pop("skip_evaluate_requested", None)
    merged["current_state"] = "Delivered"
    save_workflow_state(ws_path, merged, merge=False)

    return _success(_CMD_DELIVER, "Delivered")


def abandon_evaluation(cycle_id: str, project_root: Path) -> dict[str, Any]:
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current != _EXPECTED_ABANDON_STATE:
        return _failure_abandon(
            current,
            (
                f"abandon-evaluation 被拒绝：当前状态为 {current}，"
                f"预期状态为 {_EXPECTED_ABANDON_STATE}。"
                "请暂停执行，等待用户指示。"
            ),
        )

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    if not es_path.exists():
        return _failure_abandon(
            current,
            "abandon-evaluation 被拒绝：evaluate-state.md 不存在。"
            "请暂停执行，等待用户指示。",
        )

    eval_data = load_evaluate_state(es_path)
    eval_status = eval_data.get("eval_status", "")
    if eval_status != "abandoned":
        return _failure_abandon(
            current,
            (
                f"abandon-evaluation 被拒绝：eval_status 为 "
                f"{eval_status!r}，预期为 'abandoned'。"
                "请暂停执行，等待用户指示。"
            ),
        )

    merged = dict(state)
    merged["current_state"] = "Drafting"
    merged["skip_evaluate_requested"] = "false"
    save_workflow_state(ws_path, merged, merge=False)

    try:
        evaluate_round = int(merged.get("evaluate_round", "0"))
    except ValueError:
        evaluate_round = 0

    return _success(
        _CMD_ABANDON,
        "Drafting",
        evaluate_round=evaluate_round,
    )


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _cli() -> int:
    parser = argparse.ArgumentParser(description="tech-plan session control")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root directory",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(_CMD_START_EVALUATING, help="Transition to Evaluating")
    sub.add_parser(_CMD_READY, help="Transition to ReadyForDelivery")
    deliver_parser = sub.add_parser(_CMD_DELIVER, help="Transition to Delivered")
    deliver_parser.add_argument("--note", default="", help="Optional delivery note")
    sub.add_parser(
        _CMD_ABANDON,
        help="Transition Evaluating -> Drafting after evaluation abandoned",
    )

    args = parser.parse_args()
    project_root = args.project_root.resolve()
    cycle_id = args.cycle_id.strip()

    try:
        if args.command == _CMD_START_EVALUATING:
            return _emit(start_evaluating(cycle_id, project_root))
        if args.command == _CMD_READY:
            return _emit(ready_for_delivery(cycle_id, project_root))
        if args.command == _CMD_DELIVER:
            return _emit(deliver(cycle_id, project_root, note=args.note))
        if args.command == _CMD_ABANDON:
            return _emit(abandon_evaluation(cycle_id, project_root))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(_cli())
