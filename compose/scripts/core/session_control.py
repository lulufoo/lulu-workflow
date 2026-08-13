#!/usr/bin/env python3
"""Session control for compose orchestrators.

Subcommands:
    leave-split          Split -> Working (published ledger + holder finalize)
    ready-for-delivery   Working -> ReadyForDelivery (all L Completed; assemble package)
    return-to-working    ReadyForDelivery -> Working (--confirm)
    deliver              ReadyForDelivery -> Delivered (--confirm; consume Ready package)
    write-demand-manifest  Persist AI-enumerated demand units as <prefix>-demands.json
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
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, load_profile, resolve_profile_id  # noqa: E402
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
from cycle_delivered_refs import DeliveryInconsistent, file_digest  # noqa: E402
from human_delivery_gate_schema import write_approved  # noqa: E402
from l_ledger_schema import all_completed_unfrozen, load_l_ledger  # noqa: E402
from compose_package_control import assemble_compose_package, validate_ready_package  # noqa: E402
from revision_lock import LockTimeout, cycle_lock, revision_lock, session_lock  # noqa: E402
from session_state_schema import load_session_state  # noqa: E402
from transition_registry import is_allowed  # noqa: E402
from workflow_common import CACHE_DIR  # noqa: E402
from workflow_profile_paths import session_state_path  # noqa: E402
from workflow_state_schema import load_workflow_state, save_workflow_state  # noqa: E402
from scope_package_schema import load_scope_package  # noqa: E402

_CMD_LEAVE_SPLIT = "leave-split"
_CMD_READY = "ready-for-delivery"
_CMD_RETURN_WORKING = "return-to-working"
_CMD_DELIVER = "deliver"
_CMD_WRITE_DEMAND_MANIFEST = "write-demand-manifest"
_EXPECTED_SPLIT_STATE = "Split"
_EXPECTED_DELIVER_STATE = "ReadyForDelivery"
_EXPECTED_WORKING_STATE = "Working"



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


def _published_revision(revision_dir: Path) -> tuple[bool, str | None, dict[str, Any]]:
    try:
        ledger = load_l_ledger(revision_dir)
        package = load_scope_package(Path(revision_dir) / "scope-package.json")
    except (OSError, ValueError, FileNotFoundError) as exc:
        return False, str(exc), {}
    missing = [
        nid
        for nid in ledger["order"]
        if not (Path(revision_dir) / nid / "scope-ref.json").is_file()
    ]
    if missing:
        return False, "missing scope-ref mirrors: " + ", ".join(missing), {}
    ids = list(ledger["order"])
    details = {
        "node_ids": ids,
        "focus": ledger["focus"],
        "multi_l": len(ids) >= 2,
        "slices": len(package.get("slices") or []),
    }
    return True, None, details


def leave_split(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Leave session state Split → Working after holder finalize."""
    ss_path = project_root / session_state_path(cycle_id, profile_id, project_root)
    try:
        session = load_session_state(ss_path)
    except ValueError as exc:
        return {
            "ok": False,
            "command": _CMD_LEAVE_SPLIT,
            "code": "holder_finalize_pending",
            "error": str(exc),
            "current_state": "unknown",
        }
    if session["holder_finalized"] is not True:
        return {
            "ok": False,
            "command": _CMD_LEAVE_SPLIT,
            "code": "holder_finalize_pending",
            "error": "holder finalize is pending",
            "current_state": "Split",
        }
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    session_dir = ss_path.parent
    try:
        with session_lock(session_dir, exclusive=False):
            with revision_lock(ws_path.parent, exclusive=True):
                state = load_workflow_state(ws_path)
                current = state["current_state"]
                ok, err, details = _published_revision(ws_path.parent)
                if current == "Working":
                    if not ok:
                        return {
                            "ok": False,
                            "command": _CMD_LEAVE_SPLIT,
                            "current_state": current,
                            "error": err or "published revision not ready",
                        }
                    return _success(
                        _CMD_LEAVE_SPLIT,
                        "Working",
                        profile_id=profile_id,
                        transitioned=False,
                        **{
                            k: details[k]
                            for k in ("multi_l", "node_ids", "focus")
                            if k in details
                        },
                    )
                if current != _EXPECTED_SPLIT_STATE:
                    return _failure(_CMD_LEAVE_SPLIT, current)
                if not _require_transition(_CMD_LEAVE_SPLIT, current, "Working"):
                    return _failure(_CMD_LEAVE_SPLIT, current)
                if not ok:
                    return {
                        "ok": False,
                        "command": _CMD_LEAVE_SPLIT,
                        "current_state": current,
                        "error": err or "published revision not ready",
                    }
                merged = dict(state)
                merged["current_state"] = "Working"
                save_workflow_state(ws_path, merged, merge=False)
                return _success(
                    _CMD_LEAVE_SPLIT,
                    "Working",
                    profile_id=profile_id,
                    transitioned=True,
                    **{
                        k: details[k]
                        for k in ("multi_l", "node_ids", "focus")
                        if k in details
                    },
                )
    except LockTimeout:
        return {
            "ok": False,
            "command": _CMD_LEAVE_SPLIT,
            "code": "lock_timeout",
            "error": "lock timeout",
        }


def ready_for_delivery(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    session_dir = (
        project_root / session_state_path(cycle_id, profile_id, project_root)
    ).parent
    try:
        with session_lock(session_dir, exclusive=False):
            with revision_lock(ws_path.parent, exclusive=True):
                state = load_workflow_state(ws_path)
                current = state["current_state"]
                revision_dir = ws_path.parent
                if current == "ReadyForDelivery":
                    path, err = validate_ready_package(
                        revision_dir,
                        profile_id=profile_id,
                    )
                    if err or path is None:
                        return {
                            "ok": False,
                            "command": _CMD_READY,
                            "current_state": current,
                            "error": err or "Ready package missing or invalid",
                        }
                    return _success(
                        _CMD_READY,
                        "ReadyForDelivery",
                        profile_id=profile_id,
                        package_path=str(path),
                    )
                if current != _EXPECTED_WORKING_STATE:
                    return _failure(_CMD_READY, current)
                if not _require_transition(_CMD_READY, current, "ReadyForDelivery"):
                    return _failure(_CMD_READY, current)
                try:
                    ledger = load_l_ledger(revision_dir)
                except (OSError, ValueError, FileNotFoundError) as exc:
                    return {
                        "ok": False,
                        "command": _CMD_READY,
                        "current_state": current,
                        "error": str(exc),
                    }
                if not all_completed_unfrozen(ledger):
                    return {
                        "ok": False,
                        "command": _CMD_READY,
                        "current_state": current,
                        "error": "not all L Completed and unfrozen",
                    }
                path, err = assemble_compose_package(
                    revision_dir,
                    profile_id=profile_id,
                    require_completed=True,
                )
                if err or path is None:
                    return {
                        "ok": False,
                        "command": _CMD_READY,
                        "current_state": current,
                        "error": err or "assemble-package failed",
                    }
                merged = dict(state)
                merged["current_state"] = "ReadyForDelivery"
                save_workflow_state(ws_path, merged, merge=False)
                return _success(
                    _CMD_READY,
                    "ReadyForDelivery",
                    profile_id=profile_id,
                    package_path=str(path),
                )
    except LockTimeout:
        return {
            "ok": False,
            "command": _CMD_READY,
            "code": "lock_timeout",
            "error": "lock timeout",
        }


def return_to_working(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    confirm: bool = False,
) -> dict[str, Any]:
    if not confirm:
        return {
            "ok": False,
            "command": _CMD_RETURN_WORKING,
            "code": "confirmation_required",
            "error": "return-to-working requires --confirm",
        }
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    session_dir = (
        project_root / session_state_path(cycle_id, profile_id, project_root)
    ).parent
    try:
        with session_lock(session_dir, exclusive=False):
            with revision_lock(ws_path.parent, exclusive=True):
                state = load_workflow_state(ws_path)
                current = state["current_state"]
                if current != "ReadyForDelivery":
                    return _failure(_CMD_RETURN_WORKING, current)
                if not _require_transition(_CMD_RETURN_WORKING, current, "Working"):
                    return _failure(_CMD_RETURN_WORKING, current)
                merged = dict(state)
                merged["current_state"] = "Working"
                save_workflow_state(ws_path, merged, merge=False)
                return _success(_CMD_RETURN_WORKING, "Working", profile_id=profile_id)
    except LockTimeout:
        return {
            "ok": False,
            "command": _CMD_RETURN_WORKING,
            "code": "lock_timeout",
            "error": "lock timeout",
        }


def deliver(
    cycle_id: str,
    project_root: Path,
    *,
    note: str = "",
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    confirm: bool = False,
) -> dict[str, Any]:
    if not confirm:
        return {
            "ok": False,
            "command": _CMD_DELIVER,
            "code": "confirmation_required",
            "error": "deliver requires --confirm",
        }
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current != _EXPECTED_DELIVER_STATE:
        return _failure_deliver(current)

    if not _require_transition(_CMD_DELIVER, current, "Delivered"):
        return _failure_deliver(current)

    revision_dir = ws_path.parent
    session_dir = (
        project_root / session_state_path(cycle_id, profile_id, project_root)
    ).parent
    cycle_cache = project_root / CACHE_DIR / cycle_id
    try:
        with cycle_lock(cycle_cache, exclusive=True):
            with session_lock(session_dir, exclusive=False):
                with revision_lock(revision_dir, exclusive=True):
                    state = load_workflow_state(ws_path)
                    current = state["current_state"]
                    if current != _EXPECTED_DELIVER_STATE:
                        return _failure_deliver(current)
                    if not _require_transition(_CMD_DELIVER, current, "Delivered"):
                        return _failure_deliver(current)
                    agenda_blockers = _agenda_blocking_for_revision(revision_dir)
                    if agenda_blockers:
                        return _failure_deliver_agenda(current, agenda_blockers)
                    package_path, package_err = validate_ready_package(
                        revision_dir,
                        profile_id=profile_id,
                    )
                    if package_err or package_path is None:
                        return {
                            "ok": False,
                            "command": _CMD_DELIVER,
                            "current_state": current,
                            "code": "package_failed",
                            "error": package_err or "Ready package missing or invalid",
                            "message": (
                                "deliver blocked: Ready package missing or invalid "
                                f"({package_err or 'unknown error'})"
                            ),
                        }
                    digest = file_digest(package_path)
                    write_approved(
                        approval_gate_path(cycle_id, project_root, profile_id),
                        note=note,
                    )
                    active_doc = load_active_doc_for_profile(
                        cycle_id, project_root, profile_id
                    )
                    try:
                        record_delivered_ref(
                            cycle_id,
                            project_root,
                            delivered_type=profile_id,
                            path=str(package_path.resolve()),
                            revision=active_doc,
                            profile_id=profile_id,
                            source_workflow_state=str(ws_path.resolve()),
                            artifact="compose-package",
                            package_digest=digest,
                        )
                    except DeliveryInconsistent as exc:
                        return {
                            "ok": False,
                            "command": _CMD_DELIVER,
                            "current_state": current,
                            "code": "delivery_inconsistent",
                            "error": str(exc),
                        }
                    merged = dict(state)
                    merged["current_state"] = "Delivered"
                    save_workflow_state(ws_path, merged, merge=False)
                    return _success(_CMD_DELIVER, "Delivered", profile_id=profile_id)
    except LockTimeout:
        return {
            "ok": False,
            "command": _CMD_DELIVER,
            "code": "lock_timeout",
            "error": "lock timeout",
        }



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
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(_CMD_LEAVE_SPLIT, help="Leave session state Split -> Working")
    sub.add_parser(_CMD_READY, help="Transition to ReadyForDelivery")
    ret = sub.add_parser(_CMD_RETURN_WORKING, help="ReadyForDelivery -> Working")
    ret.add_argument("--confirm", action="store_true")
    deliver_parser = sub.add_parser(_CMD_DELIVER, help="Transition to Delivered")
    deliver_parser.add_argument("--note", default="", help="Optional delivery note")
    deliver_parser.add_argument("--confirm", action="store_true")
    manifest_parser = sub.add_parser(
        _CMD_WRITE_DEMAND_MANIFEST,
        help="Write <prefix>-demands.json from AI-enumerated units",
    )
    manifest_parser.add_argument(
        "--units-json",
        required=True,
        help='JSON array of demand units (inline or "@file"); each needs section + summary',
    )

    args = parser.parse_args()
    project_root = args.project_root.resolve()
    cycle_id = args.cycle_id.strip()
    try:
        profile_id = resolve_profile_id(
            project_root=project_root,
            cycle_id=cycle_id,
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        if args.command == _CMD_LEAVE_SPLIT:
            return _emit(leave_split(cycle_id, project_root, profile_id=profile_id))
        if args.command == _CMD_READY:
            return _emit(ready_for_delivery(cycle_id, project_root, profile_id=profile_id))
        if args.command == _CMD_RETURN_WORKING:
            return _emit(
                return_to_working(
                    cycle_id,
                    project_root,
                    profile_id=profile_id,
                    confirm=args.confirm,
                )
            )
        if args.command == _CMD_DELIVER:
            return _emit(
                deliver(
                    cycle_id,
                    project_root,
                    note=args.note,
                    profile_id=profile_id,
                    confirm=args.confirm,
                ),
            )
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
