#!/usr/bin/env python3
"""Session control for compose orchestrators (tech-plan, tech-design, …).

Subcommands:
    start-evaluating     Drafting -> Evaluating (+ evaluate-state.md init)
    ready-for-delivery   Drafting|Evaluating -> ReadyForDelivery
    deliver              ReadyForDelivery -> Delivered (+ human-delivery-gate.md)
    abandon-evaluation   Evaluating -> Drafting (requires evaluate-state abandoned)
    resume-after-eval    Evaluating -> Drafting after eval complete-round (fix exit)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_CORE = Path(__file__).resolve().parent
_SCRIPTS = _CORE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, EVAL_SCRIPTS as _EVAL_SCRIPTS  # noqa: E402

sys.path.insert(0, str(_EVAL_SCRIPTS))

from adapter_registry import load_adapter  # noqa: E402
from compose_session import (  # noqa: E402
    approval_gate_path,
    document_file_path,
    eval_workflow_id,
    load_active_doc_for_profile,
    workflow_state_path,
)
from delivered_refs_schema import record_delivered_ref  # noqa: E402
from evaluate_state_schema import load_evaluate_state  # noqa: E402
from human_delivery_gate_schema import write_approved  # noqa: E402
from session_evaluating import transition_to_evaluating  # noqa: E402
from transition_registry import is_allowed  # noqa: E402
from workflow_state_schema import load_workflow_state, save_workflow_state  # noqa: E402

_CMD_START_EVALUATING = "start-evaluating"
_CMD_READY = "ready-for-delivery"
_CMD_DELIVER = "deliver"
_CMD_ABANDON = "abandon-evaluation"
_CMD_RESUME_AFTER_EVAL = "resume-after-eval"
_EXPECTED_DELIVER_STATE = "ReadyForDelivery"
_EXPECTED_ABANDON_STATE = "Evaluating"
_EXPECTED_EVALUATING_STATE = "Evaluating"


def _evaluate_state_path(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str,
) -> Path:
    adapter = load_adapter(eval_workflow_id(profile_id))
    return adapter.resolve_evaluate_state_path(cycle_id, project_root)


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


def _require_transition(command: str, from_state: str, to_state: str) -> bool:
    return is_allowed(command, from_state, to_state)


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


def start_evaluating(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
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
            profile_id=profile_id,
            evaluate_round=evaluate_round,
        )

    if current != "Drafting":
        return _failure(_CMD_START_EVALUATING, current)

    if not _require_transition(_CMD_START_EVALUATING, current, "Evaluating"):
        return _failure(_CMD_START_EVALUATING, current)

    entry = transition_to_evaluating(cycle_id, project_root, profile_id=profile_id)
    if not entry.get("ok"):
        return {
            "ok": False,
            "command": _CMD_START_EVALUATING,
            "current_state": entry.get("current_state", current),
            "resume": entry.get(
                "resume",
                _build_resume(_CMD_START_EVALUATING, entry.get("current_state", current)),
            ),
        }

    return _success(
        _CMD_START_EVALUATING,
        "Evaluating",
        profile_id=profile_id,
        evaluate_round=entry["evaluate_round"],
    )


def ready_for_delivery(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current == "ReadyForDelivery":
        return _success(_CMD_READY, "ReadyForDelivery", profile_id=profile_id)

    if current == "Drafting":
        if not _require_transition(_CMD_READY, current, "ReadyForDelivery"):
            return _failure(_CMD_READY, current)
        updates: dict[str, str] = {"current_state": "ReadyForDelivery"}
        updates["skip_evaluate_requested"] = "true"
        save_workflow_state(ws_path, updates)
        return _success(_CMD_READY, "ReadyForDelivery", profile_id=profile_id)

    if current == "Evaluating":
        if not _require_transition(_CMD_READY, current, "ReadyForDelivery"):
            return _failure(_CMD_READY, current)
        merged = dict(state)
        merged.pop("skip_evaluate_requested", None)
        merged["current_state"] = "ReadyForDelivery"
        save_workflow_state(ws_path, merged, merge=False)
        return _success(_CMD_READY, "ReadyForDelivery", profile_id=profile_id)

    return _failure(_CMD_READY, current)


def deliver(
    cycle_id: str,
    project_root: Path,
    *,
    note: str = "",
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current != _EXPECTED_DELIVER_STATE:
        return _failure_deliver(current)

    if not _require_transition(_CMD_DELIVER, current, "Delivered"):
        return _failure_deliver(current)

    write_approved(approval_gate_path(cycle_id, project_root, profile_id), note=note)

    active_doc = load_active_doc_for_profile(cycle_id, project_root, profile_id)
    compose_path = document_file_path(cycle_id, project_root, profile_id)
    record_delivered_ref(
        cycle_id,
        project_root,
        delivered_type=profile_id,
        path=str(compose_path.resolve()),
        revision=active_doc,
        profile_id=profile_id,
        source_workflow_state=str(ws_path.resolve()),
    )

    merged = dict(state)
    merged.pop("skip_evaluate_requested", None)
    merged["current_state"] = "Delivered"
    save_workflow_state(ws_path, merged, merge=False)

    return _success(_CMD_DELIVER, "Delivered", profile_id=profile_id)


def abandon_evaluation(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
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

    es_path = _evaluate_state_path(cycle_id, project_root, profile_id=profile_id)
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

    if not _require_transition(_CMD_ABANDON, current, "Drafting"):
        return _failure_abandon(
            current,
            (
                f"abandon-evaluation 被拒绝：当前状态为 {current}，"
                f"预期状态为 {_EXPECTED_ABANDON_STATE}。"
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
        profile_id=profile_id,
        evaluate_round=evaluate_round,
    )


def resume_after_eval(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Return to Drafting after complete-round (Evaluating fix exit)."""
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    current = state["current_state"]
    if current != _EXPECTED_EVALUATING_STATE:
        return _failure(
            _CMD_RESUME_AFTER_EVAL,
            current,
        )

    try:
        evaluate_round = int(state.get("evaluate_round", "0"))
    except ValueError:
        evaluate_round = 0
    if evaluate_round < 1:
        return {
            "ok": False,
            "command": _CMD_RESUME_AFTER_EVAL,
            "current_state": current,
            "reason": f"evaluate_round is {evaluate_round!r} (expected >= 1).",
        }

    es_path = _evaluate_state_path(cycle_id, project_root, profile_id=profile_id)
    if not es_path.exists():
        return {
            "ok": False,
            "command": _CMD_RESUME_AFTER_EVAL,
            "current_state": current,
            "reason": "evaluate-state.md not found.",
        }

    eval_data = load_evaluate_state(es_path)
    eval_status = eval_data.get("eval_status", "")
    if eval_status == "abandoned":
        return {
            "ok": False,
            "command": _CMD_RESUME_AFTER_EVAL,
            "current_state": current,
            "reason": "evaluation was abandoned (eval_status: abandoned).",
        }
    if eval_status != "done":
        return {
            "ok": False,
            "command": _CMD_RESUME_AFTER_EVAL,
            "current_state": current,
            "reason": (
                f"eval_status is {eval_status!r}, "
                "expected 'done' (run complete-round first)."
            ),
        }

    if not _require_transition(_CMD_RESUME_AFTER_EVAL, current, "Drafting"):
        return _failure(_CMD_RESUME_AFTER_EVAL, current)

    merged = dict(state)
    merged["current_state"] = "Drafting"
    merged.pop("skip_evaluate_requested", None)
    save_workflow_state(ws_path, merged, merge=False)

    return _success(
        _CMD_RESUME_AFTER_EVAL,
        "Drafting",
        profile_id=profile_id,
        evaluate_round=evaluate_round,
    )


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _cli() -> int:
    parser = argparse.ArgumentParser(description="compose session control")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root directory",
    )
    parser.add_argument(
        "--profile",
        default=DEFAULT_COMPOSE_PROFILE_ID,
        help="Compose profile / stage name (default: tech-plan)",
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
    sub.add_parser(
        _CMD_RESUME_AFTER_EVAL,
        help="Transition Evaluating -> Drafting after complete-round (fix exit)",
    )

    args = parser.parse_args()
    project_root = args.project_root.resolve()
    cycle_id = args.cycle_id.strip()
    profile_id = args.profile.strip()

    try:
        if args.command == _CMD_START_EVALUATING:
            return _emit(start_evaluating(cycle_id, project_root, profile_id=profile_id))
        if args.command == _CMD_READY:
            return _emit(ready_for_delivery(cycle_id, project_root, profile_id=profile_id))
        if args.command == _CMD_DELIVER:
            return _emit(
                deliver(cycle_id, project_root, note=args.note, profile_id=profile_id),
            )
        if args.command == _CMD_ABANDON:
            return _emit(abandon_evaluation(cycle_id, project_root, profile_id=profile_id))
        if args.command == _CMD_RESUME_AFTER_EVAL:
            return _emit(resume_after_eval(cycle_id, project_root, profile_id=profile_id))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(_cli())
