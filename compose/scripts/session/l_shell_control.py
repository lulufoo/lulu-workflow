#!/usr/bin/env python3
"""Outer-shell CLI for ordered L management.

Subcommands:
    status
    view --target Lx
    advance
    backtrack --target Lx --confirm
    unfreeze --expected-fingerprint <sha256> --confirm

Design rationale:
docs/domain/archive/compose/archive-33.0/compose-outer-shell-management-subdesign.md

Stdout contracts live in this module docstring / ``--help``.
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

from compose_session import workflow_state_path  # noqa: E402
from l_ledger_schema import (  # noqa: E402
    all_completed_unfrozen,
    l_ledger_path,
    ledger_fingerprint,
    load_l_ledger,
    save_l_ledger,
)
from l_transition_kernel import (  # noqa: E402
    IllegalTransitionError,
    shell_advance,
    shell_backtrack,
    shell_unfreeze,
)
from revision_lock import LockTimeoutError, revision_lock, session_lock  # noqa: E402
from workflow_paths import resolve_profile_id  # noqa: E402
from workflow_profile_paths import session_state_path  # noqa: E402
from workflow_state_schema import load_workflow_state  # noqa: E402

_CMD_STATUS = "status"
_CMD_VIEW = "view"
_CMD_ADVANCE = "advance"
_CMD_BACKTRACK = "backtrack"
_CMD_UNFREEZE = "unfreeze"


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _failure(command: str, code: str, error: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "command": command,
        "code": code,
        "error": error,
    }
    payload.update(extra)
    return payload


def derive_next_actions(ledger: dict[str, Any], session_state: str) -> list[str]:
    """Cognitive map. Not a second copy of ledger state."""
    if session_state == "Split":
        return ["leave-split", "view"]
    if session_state == "ReadyForDelivery":
        return ["deliver", "return-to-working", "view"]
    if session_state in {"Delivered", "Invalidated"}:
        return ["view"]
    if session_state != "Working":
        return ["view"]

    order = list(ledger["order"])
    focus = str(ledger["focus"])
    f = order.index(focus)
    cell = ledger["by_id"][focus]
    actions: list[str] = ["view"]
    if cell["state"] != "Completed":
        actions.append("execute-current")
    else:
        actions.append("reopen-current")
        if f + 1 < len(order):
            nxt = ledger["by_id"][order[f + 1]]
            if nxt["frozen"] is True:
                actions.append("align-next")
            else:
                actions.append("advance")
        if all_completed_unfrozen(ledger):
            actions.append("ready-for-delivery")
    if any(
        ledger["by_id"][nid]["state"] == "Completed"
        and ledger["by_id"][nid]["frozen"] is False
        and order.index(nid) < f
        for nid in order
    ):
        actions.append("backtrack")
    return actions


def _status_body(ledger: dict[str, Any], session_state: str) -> dict[str, Any]:
    order = list(ledger["order"])
    focus = str(ledger["focus"])
    f = order.index(focus)
    nxt = None
    if f + 1 < len(order):
        nid = order[f + 1]
        cell = ledger["by_id"][nid]
        nxt = {"id": nid, "state": cell["state"], "frozen": cell["frozen"]}
    current = ledger["by_id"][focus]
    return {
        "ok": True,
        "command": _CMD_STATUS,
        "session_state": session_state,
        "ledger_fingerprint": ledger_fingerprint(ledger),
        "order": order,
        "focus": focus,
        "by_id": ledger["by_id"],
        "current": {"id": focus, "state": current["state"]},
        "next": nxt,
        "ready_for_delivery": all_completed_unfrozen(ledger),
        "next_actions": derive_next_actions(ledger, session_state),
    }


def cmd_status(revision_dir: Path, session_state: str) -> dict[str, Any]:
    path = l_ledger_path(revision_dir)
    if not path.is_file():
        return _failure(
            _CMD_STATUS,
            "unsupported_revision",
            "missing l-ledger.json; open a new revision",
        )
    ledger = load_l_ledger(revision_dir)
    return _status_body(ledger, session_state)


def cmd_view(revision_dir: Path, target: str) -> dict[str, Any]:
    path = l_ledger_path(revision_dir)
    if not path.is_file():
        return _failure(
            _CMD_VIEW,
            "unsupported_revision",
            "missing l-ledger.json; open a new revision",
        )
    ledger = load_l_ledger(revision_dir)
    if target not in ledger["order"]:
        return _failure(_CMD_VIEW, "illegal_transition", f"unknown target {target}")
    cell = ledger["by_id"][target]
    slice_dir = Path(revision_dir) / target
    source = None
    scope_ref = slice_dir / "scope-ref.json"
    if scope_ref.is_file():
        try:
            source = json.loads(scope_ref.read_text(encoding="utf-8")).get("source_path")
        except (OSError, json.JSONDecodeError, TypeError):
            source = None
    return {
        "ok": True,
        "command": _CMD_VIEW,
        "target": target,
        "state": cell["state"],
        "frozen": cell["frozen"],
        "slice_dir": str(slice_dir.resolve()),
        "scope_ref_path": str(scope_ref.resolve()),
        "source_path": source,
    }


def _mutate(
    command: str,
    revision_dir: Path,
    session_state: str,
    apply,
) -> dict[str, Any]:
    if session_state != "Working":
        return _failure(
            command,
            "wrong_session_state",
            f"{command} requires Working",
            session_state=session_state,
        )
    path = l_ledger_path(revision_dir)
    if not path.is_file():
        return _failure(
            command,
            "unsupported_revision",
            "missing l-ledger.json; open a new revision",
        )
    try:
        with revision_lock(revision_dir, exclusive=True):
            ledger = load_l_ledger(revision_dir)
            new_ledger = apply(ledger)
            save_l_ledger(revision_dir, new_ledger)
            return {
                "ok": True,
                "command": command,
                "ledger_fingerprint": ledger_fingerprint(new_ledger),
                "focus": new_ledger["focus"],
                "by_id": new_ledger["by_id"],
                "next_actions": derive_next_actions(new_ledger, session_state),
            }
    except LockTimeoutError:
        return _failure(command, "lock_timeout", "revision lock timeout")
    except IllegalTransitionError as exc:
        extra = dict(exc.extra)
        if exc.code == "alignment_required":
            extra["ledger_fingerprint"] = ledger_fingerprint(load_l_ledger(revision_dir))
        return _failure(command, exc.code, str(exc), **extra)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _failure(command, "invalid_ledger", str(exc))


def _open_point_txn_block(slice_dir: Path) -> str | None:
    txn_path = Path(slice_dir) / "_open-point-txn.json"
    if not txn_path.is_file():
        return None
    from compose_state_lock import compose_state_lock  # noqa: WPS433

    inductive = _SCRIPTS / "inductive"
    for path in (inductive, *kernel_bootstrap.inductive_schema_dirs()):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from open_point_store import RepairRequiredError, reconcile  # noqa: WPS433

    try:
        with compose_state_lock(slice_dir):
            reconcile(slice_dir)
            if txn_path.is_file():
                return "pending open-point transaction"
    except RepairRequiredError:
        return "open-point transaction repair_required"
    return None


def cmd_advance(revision_dir: Path, session_state: str) -> dict[str, Any]:
    if session_state != "Working":
        return _failure(
            _CMD_ADVANCE,
            "wrong_session_state",
            f"{_CMD_ADVANCE} requires Working",
            session_state=session_state,
        )
    path = l_ledger_path(revision_dir)
    if not path.is_file():
        return _failure(
            _CMD_ADVANCE,
            "unsupported_revision",
            "missing l-ledger.json; open a new revision",
        )
    try:
        with revision_lock(revision_dir, exclusive=True):
            ledger = load_l_ledger(revision_dir)
            txn_err = _open_point_txn_block(
                (Path(revision_dir) / str(ledger["focus"])).resolve()
            )
            if txn_err:
                return _failure(_CMD_ADVANCE, "open_point_txn_pending", txn_err)
            result = shell_advance(ledger)
            if result.changed:
                save_l_ledger(revision_dir, result.ledger)
            out = result.ledger
            payload = {
                "ok": True,
                "command": _CMD_ADVANCE,
                "changed": result.changed,
                "ledger_fingerprint": ledger_fingerprint(out),
                "focus": out["focus"],
                "by_id": out["by_id"],
                "next_actions": derive_next_actions(out, session_state),
            }
            if result.next_action:
                payload["next_action"] = result.next_action
            return payload
    except LockTimeoutError:
        return _failure(_CMD_ADVANCE, "lock_timeout", "revision lock timeout")
    except IllegalTransitionError as exc:
        extra = dict(exc.extra)
        if exc.code == "alignment_required":
            extra["ledger_fingerprint"] = ledger_fingerprint(load_l_ledger(revision_dir))
        return _failure(_CMD_ADVANCE, exc.code, str(exc), **extra)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _failure(_CMD_ADVANCE, "invalid_ledger", str(exc))


def cmd_backtrack(
    revision_dir: Path,
    session_state: str,
    target: str,
    *,
    confirm: bool,
) -> dict[str, Any]:
    if not confirm:
        return _failure(
            _CMD_BACKTRACK,
            "confirmation_required",
            "backtrack requires --confirm",
        )
    return _mutate(
        _CMD_BACKTRACK,
        revision_dir,
        session_state,
        lambda ledger: shell_backtrack(ledger, target),
    )


def cmd_unfreeze(
    revision_dir: Path,
    session_state: str,
    expected_fingerprint: str,
    *,
    confirm: bool,
) -> dict[str, Any]:
    if not confirm:
        return _failure(
            _CMD_UNFREEZE,
            "confirmation_required",
            "unfreeze requires --confirm",
        )

    def apply(ledger: dict[str, Any]) -> dict[str, Any]:
        current = ledger_fingerprint(ledger)
        if current != expected_fingerprint:
            raise IllegalTransitionError(
                "stale_fingerprint",
                "expected fingerprint does not match current ledger",
            )
        return shell_unfreeze(ledger)

    return _mutate(_CMD_UNFREEZE, revision_dir, session_state, apply)


def _load_session_state(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> tuple[str, Path]:
    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    return str(state["current_state"]), ws_path.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compose L-shell (ordered chain)")
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser(_CMD_STATUS)
    view = sub.add_parser(_CMD_VIEW)
    view.add_argument("--target", required=True)
    sub.add_parser(_CMD_ADVANCE)
    back = sub.add_parser(_CMD_BACKTRACK)
    back.add_argument("--target", required=True)
    back.add_argument("--confirm", action="store_true")
    unf = sub.add_parser(_CMD_UNFREEZE)
    unf.add_argument("--expected-fingerprint", required=True)
    unf.add_argument("--confirm", action="store_true")
    args = parser.parse_args(argv)

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
        session_state, revision_dir = _load_session_state(
            cycle_id,
            project_root,
            profile_id,
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _emit(
            _failure(args.command, "wrong_session_state", str(exc))
        )

    session_dir = session_state_path(
        cycle_id,
        profile_id,
        project_root,
    ).parent
    try:
        with session_lock(session_dir, exclusive=False):
            if args.command == _CMD_STATUS:
                with revision_lock(revision_dir, exclusive=False):
                    return _emit(cmd_status(revision_dir, session_state))
            if args.command == _CMD_VIEW:
                with revision_lock(revision_dir, exclusive=False):
                    return _emit(cmd_view(revision_dir, args.target))
            if args.command == _CMD_ADVANCE:
                return _emit(cmd_advance(revision_dir, session_state))
            if args.command == _CMD_BACKTRACK:
                return _emit(
                    cmd_backtrack(
                        revision_dir,
                        session_state,
                        args.target,
                        confirm=args.confirm,
                    )
                )
            if args.command == _CMD_UNFREEZE:
                return _emit(
                    cmd_unfreeze(
                        revision_dir,
                        session_state,
                        args.expected_fingerprint,
                        confirm=args.confirm,
                    )
                )
    except LockTimeoutError:
        return _emit(_failure(args.command, "lock_timeout", "session lock timeout"))
    return _emit(_failure(args.command, "illegal_transition", "unknown command"))


if __name__ == "__main__":
    raise SystemExit(main())
