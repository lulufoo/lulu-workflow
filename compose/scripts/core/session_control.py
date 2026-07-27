#!/usr/bin/env python3
"""Session control for compose orchestrators.

Subcommands:
    split-complete       Split -> Working (requires check-split-ready topology)
    start-evaluating     Working: set focus phase=evaluating (session stays Working)
    ready-for-delivery   Working -> ReadyForDelivery (all L accepted; no skip-eval)
    deliver              ReadyForDelivery -> Delivered (+ human-delivery-gate.md)
    abandon-evaluation   Working: focus phase evaluating->in_progress (eval abandoned)
    resume-after-eval    Working: focus phase evaluating->in_progress (Fix L / after complete-round)
    write-demand-manifest  Persist AI-enumerated demand units as <prefix>-demands.json
                           (producer profiles with a demand_manifest block only)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_CORE = Path(__file__).resolve().parent
_SCRIPTS = _CORE.parent
_AGENDA_SCRIPTS = _SCRIPTS.parent.parent / "agenda" / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_AGENDA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_AGENDA_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, load_profile  # noqa: E402
from agenda_schema import agenda_path, blocking_items, load_agenda  # noqa: E402

from compose_session import (  # noqa: E402
    approval_gate_path,
    document_file_path,
    load_active_doc_for_profile,
    workflow_state_path,
)
from demand_manifest_schema import (  # noqa: E402
    build_manifest,
    manifest_filename,
    parse_units,
    write_manifest,
)
from delivered_refs_schema import record_delivered_ref  # noqa: E402
from human_delivery_gate_schema import write_approved  # noqa: E402
from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import parse_frontmatter_fields  # noqa: E402
from workflow_profile_paths import evaluate_state_path as profile_evaluate_state_path  # noqa: E402
from multi_slice_control import (  # noqa: E402
    assemble_compose_package,
    evaluate_split_ready,
)
from session_evaluating import enter_evaluating_state  # noqa: E402
from discussion_pointer_schema import (  # noqa: E402
    all_l_accepted,
    load_discussion_pointer,
    save_discussion_pointer,
)
from dependency_tree_schema import load_dependency_tree  # noqa: E402
from transition_registry import is_allowed  # noqa: E402
from workflow_state_schema import load_workflow_state, save_workflow_state  # noqa: E402

_CMD_SPLIT_COMPLETE = "split-complete"
_CMD_START_EVALUATING = "start-evaluating"
_CMD_READY = "ready-for-delivery"
_CMD_DELIVER = "deliver"
_CMD_ABANDON = "abandon-evaluation"
_CMD_RESUME_AFTER_EVAL = "resume-after-eval"
_CMD_WRITE_DEMAND_MANIFEST = "write-demand-manifest"
_EXPECTED_SPLIT_STATE = "Split"
_EXPECTED_DELIVER_STATE = "ReadyForDelivery"
_EXPECTED_WORKING_STATE = "Working"



def _evaluate_state_path(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str,
) -> Path:
    active_doc = load_active_doc_from_cycle(
        cycle_id,
        project_root,
        profile_id=profile_id,
    )
    rel = profile_evaluate_state_path(cycle_id, active_doc, profile_id, project_root)
    return project_root / rel


def _read_eval_status(es_path: Path) -> str:
    if not es_path.is_file():
        return ""
    content = es_path.read_text(encoding="utf-8")
    return parse_frontmatter_fields(content).get("eval_status", "")


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


def _failure_deliver_agenda(
    current_state: str,
    blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    ids = [str(b.get("id", "")) for b in blockers]
    return {
        "ok": False,
        "command": _CMD_DELIVER,
        "current_state": current_state,
        "message": (
            "deliver 被拒绝：阶段议程存在未解除的 blocker "
            f"({', '.join(ids)})。请 released / waived(+reason) / async 后再 deliver。"
        ),
        "agenda_blocking": blockers,
    }


def _agenda_blocking_for_revision(revision_dir: Path) -> list[dict[str, Any]]:
    """Missing agenda.json ⇒ empty (do not fail deliver)."""
    data = load_agenda(agenda_path(revision_dir))
    return blocking_items(data)


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


def _set_focus_phase_in_progress(revision_dir: Path) -> dict[str, Any]:
    """Move focus L from evaluating -> in_progress. Returns focus/phase info."""
    tree = load_dependency_tree(revision_dir)
    pointer = load_discussion_pointer(revision_dir)
    focus = str(pointer["focus"])
    cell = pointer["by_id"][focus]
    if cell.get("phase") == "evaluating":
        cell["phase"] = "in_progress"
        cell["acceptance"] = "pending"
        save_discussion_pointer(revision_dir, pointer, tree=tree)
    return {"focus": focus, "phase": pointer["by_id"][focus]["phase"]}


def split_complete(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Split → Working after topology is locked (check-split-ready)."""
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current == "Working":
        ok, err, details = evaluate_split_ready(ws_path.parent)
        if not ok:
            return {
                "ok": False,
                "command": _CMD_SPLIT_COMPLETE,
                "current_state": current,
                "error": err or "split topology not ready",
                "resume": {
                    "entry": current,
                    "action": (
                        "会话已在 Working，但拓扑未就绪；请补 lock 树或新开 revision。"
                        f" ({err})"
                    ),
                },
            }
        return _success(
            _CMD_SPLIT_COMPLETE,
            "Working",
            profile_id=profile_id,
            transitioned=False,
            **{k: details[k] for k in ("multi_l", "node_ids", "focus") if k in details},
        )

    if current != _EXPECTED_SPLIT_STATE:
        return _failure(_CMD_SPLIT_COMPLETE, current)

    if not _require_transition(_CMD_SPLIT_COMPLETE, current, "Working"):
        return _failure(_CMD_SPLIT_COMPLETE, current)

    ok, err, details = evaluate_split_ready(ws_path.parent)
    if not ok:
        return {
            "ok": False,
            "command": _CMD_SPLIT_COMPLETE,
            "current_state": current,
            "error": err or "split topology not ready",
            "resume": {
                "entry": current,
                "action": (
                    "Split 未完成：请先 lock 依赖树（单需求 = 显式 L1），"
                    f"再 split-complete。 ({err})"
                ),
            },
        }

    merged = dict(state)
    merged["current_state"] = "Working"
    save_workflow_state(ws_path, merged, merge=False)
    return _success(
        _CMD_SPLIT_COMPLETE,
        "Working",
        profile_id=profile_id,
        transitioned=True,
        **{k: details[k] for k in ("multi_l", "node_ids", "focus") if k in details},
    )


def start_evaluating(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Set focus phase=evaluating; session stays Working."""
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current != _EXPECTED_WORKING_STATE:
        return _failure(_CMD_START_EVALUATING, current)

    topo_ok, topo_err, _ = evaluate_split_ready(ws_path.parent)
    if not topo_ok:
        return {
            "ok": False,
            "command": _CMD_START_EVALUATING,
            "current_state": current,
            "error": topo_err or "split topology not ready",
            "resume": {
                "entry": current,
                "action": (
                    "无 locked 拓扑，不能进入 L evaluating；请回到 Split 补 lock "
                    f"或新开 revision。 ({topo_err})"
                ),
            },
        }

    entry = enter_evaluating_state(cycle_id, project_root, profile_id=profile_id)
    if not entry.get("ok"):
        return {
            "ok": False,
            "command": _CMD_START_EVALUATING,
            "current_state": entry.get("current_state", current),
            "resume": entry.get(
                "resume",
                _build_resume(
                    _CMD_START_EVALUATING, entry.get("current_state", current)
                ),
            ),
        }

    return _success(
        _CMD_START_EVALUATING,
        "Working",
        profile_id=profile_id,
        evaluate_round=entry["evaluate_round"],
        focus=entry.get("focus"),
        phase=entry.get("phase"),
        transitioned=entry.get("transitioned"),
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

    if current != _EXPECTED_WORKING_STATE:
        return _failure(_CMD_READY, current)

    if not _require_transition(_CMD_READY, current, "ReadyForDelivery"):
        return _failure(_CMD_READY, current)

    revision_dir = ws_path.parent
    try:
        pointer = load_discussion_pointer(revision_dir)
    except (FileNotFoundError, ValueError) as exc:
        return {
            "ok": False,
            "command": _CMD_READY,
            "current_state": current,
            "error": str(exc),
            "resume": {
                "entry": current,
                "action": f"无法读取 discussion-pointer：{exc}",
            },
        }

    if not all_l_accepted(pointer):
        return {
            "ok": False,
            "command": _CMD_READY,
            "current_state": current,
            "error": "not all L accepted (phase=accepted required)",
            "resume": {
                "entry": current,
                "action": (
                    "尚未全员 accepted，不能 ReadyForDelivery；"
                    "请完成各 L 评估（Accept L）。skip-eval 已禁止。"
                ),
            },
        }

    merged = dict(state)
    merged["current_state"] = "ReadyForDelivery"
    save_workflow_state(ws_path, merged, merge=False)
    return _success(_CMD_READY, "ReadyForDelivery", profile_id=profile_id)


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

    revision_dir = ws_path.parent
    agenda_blockers = _agenda_blocking_for_revision(revision_dir)
    if agenda_blockers:
        return _failure_deliver_agenda(current, agenda_blockers)

    write_approved(approval_gate_path(cycle_id, project_root, profile_id), note=note)

    active_doc = load_active_doc_for_profile(cycle_id, project_root, profile_id)
    package_path, package_err = assemble_compose_package(
        revision_dir,
        profile_id=profile_id,
        require_acceptance_done=True,
    )
    if package_err or package_path is None:
        return {
            "ok": False,
            "command": _CMD_DELIVER,
            "current_state": current,
            "error": package_err or "assemble-package failed",
            "message": (
                f"deliver blocked: cannot assemble *-package.json "
                f"({package_err or 'unknown error'})"
            ),
        }
    record_delivered_ref(
        cycle_id,
        project_root,
        delivered_type=profile_id,
        path=str(package_path.resolve()),
        revision=active_doc,
        profile_id=profile_id,
        source_workflow_state=str(ws_path.resolve()),
    )

    merged = dict(state)
    merged["current_state"] = "Delivered"
    save_workflow_state(ws_path, merged, merge=False)

    return _success(_CMD_DELIVER, "Delivered", profile_id=profile_id)



def write_demand_manifest(
    cycle_id: str,
    project_root: Path,
    *,
    units_json: str,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Persist an AI-enumerated demand list as ``<prefix>-demands.json``.

    Mechanical only: the AI performs the semantic atomization and passes the
    units via ``--units-json``; this step mints ids, validates, and writes the
    manifest beside the delivered document. Stages without a ``demand_manifest``
    profile block are a no-op (degrade invariant, design §5.11).
    """
    profile = load_profile(profile_id, project_root=project_root, cycle_id=cycle_id)
    block = profile.get("demand_manifest")
    if not isinstance(block, dict) or not block:
        return {
            "ok": True,
            "command": _CMD_WRITE_DEMAND_MANIFEST,
            "skipped": True,
            "profile_id": profile_id,
            "reason": (
                f"profile {profile_id!r} declares no demand_manifest block; "
                "no manifest produced"
            ),
        }

    id_prefix = str(block.get("id_prefix", "")).strip()
    if not id_prefix:
        return {
            "ok": False,
            "command": _CMD_WRITE_DEMAND_MANIFEST,
            "profile_id": profile_id,
            "reason": "demand_manifest.id_prefix is missing or empty in the profile",
        }

    units = parse_units(units_json)
    manifest = build_manifest(units, id_prefix)
    doc_path = document_file_path(cycle_id, project_root, profile_id)
    out_path = doc_path.parent / manifest_filename(id_prefix)
    write_manifest(out_path, manifest)

    return {
        "ok": True,
        "command": _CMD_WRITE_DEMAND_MANIFEST,
        "profile_id": profile_id,
        "id_prefix": id_prefix,
        "path": str(out_path.resolve()),
        "demand_count": len(manifest["demands"]),
    }


def abandon_evaluation(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Focus evaluating → in_progress after evaluate-state abandoned; stay Working."""
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current != _EXPECTED_WORKING_STATE:
        return _failure_abandon(
            current,
            (
                f"abandon-evaluation 被拒绝：当前状态为 {current}，"
                f"预期状态为 {_EXPECTED_WORKING_STATE}。"
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

    eval_status = _read_eval_status(es_path)
    if eval_status != "abandoned":
        return _failure_abandon(
            current,
            (
                f"abandon-evaluation 被拒绝：eval_status 为 "
                f"{eval_status!r}，预期为 'abandoned'。"
                "请暂停执行，等待用户指示。"
            ),
        )

    try:
        phase_info = _set_focus_phase_in_progress(ws_path.parent)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        return _failure_abandon(current, f"abandon-evaluation 被拒绝：{exc}")

    merged = dict(state)
    merged["current_state"] = "Working"
    save_workflow_state(ws_path, merged, merge=False)

    try:
        evaluate_round = int(merged.get("evaluate_round", "0"))
    except ValueError:
        evaluate_round = 0

    return _success(
        _CMD_ABANDON,
        "Working",
        profile_id=profile_id,
        evaluate_round=evaluate_round,
        **phase_info,
    )


def resume_after_eval(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Fix L: focus evaluating → in_progress after complete-round; stay Working."""
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    current = state["current_state"]
    if current != _EXPECTED_WORKING_STATE:
        return _failure(_CMD_RESUME_AFTER_EVAL, current)

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

    eval_status = _read_eval_status(es_path)
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

    try:
        phase_info = _set_focus_phase_in_progress(ws_path.parent)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        return {
            "ok": False,
            "command": _CMD_RESUME_AFTER_EVAL,
            "current_state": current,
            "reason": str(exc),
        }

    merged = dict(state)
    merged["current_state"] = "Working"
    save_workflow_state(ws_path, merged, merge=False)

    return _success(
        _CMD_RESUME_AFTER_EVAL,
        "Working",
        profile_id=profile_id,
        evaluate_round=evaluate_round,
        **phase_info,
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
        help="Compose profile / stage name (default: lulu-plan)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        _CMD_SPLIT_COMPLETE,
        help="Transition Split -> Working after topology lock",
    )
    sub.add_parser(_CMD_START_EVALUATING, help="Set focus phase=evaluating (stay Working)")
    sub.add_parser(_CMD_READY, help="Transition to ReadyForDelivery")
    deliver_parser = sub.add_parser(_CMD_DELIVER, help="Transition to Delivered")
    deliver_parser.add_argument("--note", default="", help="Optional delivery note")
    sub.add_parser(
        _CMD_ABANDON,
        help="Focus evaluating->in_progress after eval abandoned (stay Working)",
    )
    sub.add_parser(
        _CMD_RESUME_AFTER_EVAL,
        help="Focus evaluating->in_progress after complete-round / Fix L (stay Working)",
    )
    manifest_parser = sub.add_parser(
        _CMD_WRITE_DEMAND_MANIFEST,
        help="Write <prefix>-demands.json from AI-enumerated units (producer profiles only)",
    )
    manifest_parser.add_argument(
        "--units-json",
        required=True,
        help='JSON array of demand units (inline or "@file"); each needs section + summary',
    )

    args = parser.parse_args()
    project_root = args.project_root.resolve()
    cycle_id = args.cycle_id.strip()
    profile_id = args.profile.strip()

    try:
        if args.command == _CMD_SPLIT_COMPLETE:
            return _emit(split_complete(cycle_id, project_root, profile_id=profile_id))
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
        if args.command == _CMD_WRITE_DEMAND_MANIFEST:
            return _emit(
                write_demand_manifest(
                    cycle_id,
                    project_root,
                    units_json=args.units_json,
                    profile_id=profile_id,
                ),
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(_cli())
