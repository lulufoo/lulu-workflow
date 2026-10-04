#!/usr/bin/env python3
"""Approach outer-shell control.

Macro transition::

    Session → PackageReady

After the session is Completed, enter PackageReady and pass ``--confirm`` on
``deliver``. The caller does not ask again.

CLI (stdout JSON ``{"ok": true, ...}``; errors on stderr, exit 1)::

    python3 approach_shell_control.py --approach-root <path> <subcommand> ...

Subcommands: init-shell, enter, reopen, complete-reopen, recover-binding,
enter-package-ready, deliver (alias confirm-seal).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent
_SCHEMA = _SCRIPTS / "schema"
_WORKFLOW_SCRIPTS = _SCRIPTS.parents[1] / "scripts"
_DECISION_SCRIPTS = _SCRIPTS.parents[1] / "decision" / "scripts"
for _p in (_SCRIPTS, _SCHEMA, _WORKFLOW_SCRIPTS, _DECISION_SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
from project_root import apply_project_root_arg  # noqa: E402

from approach_node_binding_schema import (  # noqa: E402
    build_node_binding,
    load_node_binding,
    new_binding_id,
    node_binding_path,
    save_node_binding,
    try_load_node_binding,
)
from approach_layout import (  # noqa: E402
    decision_package_path,
    ensure_approach_layout,
    source_package_path,
)
from approach_reopen_schema import (  # noqa: E402
    build_reopen,
    load_reopen,
    new_transaction_id,
    save_reopen,
)
from approach_shell_schema import initial_shell, load_shell, save_shell, shell_path  # noqa: E402
from cycle_delivered_refs import delivered_refs_file_path, record_delivered_ref  # noqa: E402
from decision_package_schema import (  # noqa: E402
    build_decision_package,
    load_decision_package,
    save_decision_package,
)
from dec_lifecycle import bind_session  # noqa: E402
from transition_table import next_steps_for_stage  # noqa: E402
import resolve_context  # noqa: E402

_SESSION_STATE = "session-state.md"
_ACTIVE_SESSION = "."
_RECOVER_ACTIONS = frozenset({"compensate-active", "cancel"})


def init_shell(approach_root: Path) -> dict[str, Any]:
    """Create the approach root and the initial session shell pointer."""
    root = ensure_approach_layout(approach_root)
    shell = initial_shell()
    save_shell(root, shell)
    return shell


def _parse_session_state_current(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    for line in text[3:end].splitlines():
        if line.startswith("current_state:"):
            return line.split(":", 1)[1].strip()
    return None


def _session_completed(approach_root: Path) -> bool:
    state = _parse_session_state_current(Path(approach_root).resolve() / _SESSION_STATE)
    if state == "Frozen":
        return False
    return state in {"Completed", "Delivered"}


def _active_session_name(approach_root: Path) -> str | None:
    path = Path(approach_root).resolve() / "active-session.json"
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("active-session must be a JSON object")
    session_dir = str(data.get("session_dir", "")).strip()
    if session_dir == _ACTIVE_SESSION:
        return session_dir
    raise ValueError(f"active-session has invalid session_dir {session_dir!r}")


def _require_no_unrecovered_binding(approach_root: Path) -> None:
    existing = try_load_node_binding(approach_root)
    if existing is None or existing["state"] == "bound":
        return
    raise ValueError(
        "node binding blocked: unresolved transaction "
        f"{existing['binding_id']!r} is {existing['state']!r}; use recover-binding"
    )


def _start_binding(approach_root: Path, *, operation: str) -> dict[str, Any]:
    _require_no_unrecovered_binding(approach_root)
    shell = load_shell(approach_root)
    binding = build_node_binding(
        binding_id=new_binding_id(),
        state="preparing",
        previous={
            "focus": None,
            "active_session": _active_session_name(approach_root),
        },
        target={"node_id": _ACTIVE_SESSION, "session_dir": _ACTIVE_SESSION},
        operation=operation,
    )
    save_node_binding(approach_root, binding)
    return binding


def _save_failed_binding(approach_root: Path, binding: dict[str, Any]) -> None:
    binding["state"] = "failed"
    save_node_binding(approach_root, binding)


def _snapshot_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bind_session(
    approach_root: Path,
    *,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
    binding: dict[str, Any],
) -> dict[str, Any]:
    """Bind session context and the Active Session."""
    root = Path(approach_root).resolve()
    session_dir = root
    try:
        snapshot_path = resolve_context.write_resolved_context(
            Path(project_root).resolve(),
            str(cycle_id).strip(),
            Path(constraints_path).resolve(),
            session_dir=session_dir,
            binding_id=binding["binding_id"],
        )
        binding["context_snapshot"] = {
            "path": snapshot_path.resolve().as_posix(),
            "sha256": _snapshot_sha256(snapshot_path),
        }
        save_node_binding(root, binding)
        mode = (
            "existing"
            if (session_dir / "gate-state.json").is_file()
            or (session_dir / "domain-constraints.json").is_file()
            else "initialize"
        )
        decision = bind_session(
            Path(project_root).resolve(),
            str(cycle_id).strip(),
            session_dir=session_dir,
            resolved_context_path=snapshot_path,
            mode=mode,
            constraints_path=Path(constraints_path).resolve(),
        )
    except (FileNotFoundError, ValueError, OSError):
        _save_failed_binding(root, binding)
        raise
    binding["state"] = "decision_bound"
    save_node_binding(root, binding)
    return {
        "decision": decision,
        "context_snapshot": dict(binding["context_snapshot"]),
    }


def enter_session(
    approach_root: Path,
    *,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> dict[str, Any]:
    """Bind session context and the Active Session."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    if shell["macro_state"] != "Session":
        raise ValueError(
            f"enter requires macro_state=Session, got {shell['macro_state']!r}"
        )
    binding = _start_binding(root, operation="enter")
    result = _bind_session(
        root,
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=constraints_path,
        binding=binding,
    )
    save_shell(root, shell)
    binding["state"] = "bound"
    save_node_binding(root, binding)
    return {
        "ok": True,
        "command": "enter",
        "binding_id": binding["binding_id"],
        "session_dir": result["decision"]["session_dir"],
        "context_docs": result["decision"]["context_docs"],
        "context_snapshot": result["context_snapshot"],
        "initialized": result["decision"]["initialized"],
        "shell": shell,
    }


def _permit_path(approach_root: Path, binding_id: str) -> Path:
    return Path(approach_root).resolve() / "bindings" / binding_id / "permit.json"


def _issue_reopen_permit(approach_root: Path, binding: dict[str, Any], cycle_id: str) -> Path:
    path = _permit_path(approach_root, binding["binding_id"])
    payload = {
        "version": "1",
        "kind": "lulu-approach-reopen",
        "binding_id": binding["binding_id"],
        "cycle_id": str(cycle_id).strip(),
        "stage": "lulu-approach",
        "node_id": _ACTIVE_SESSION,
        "session_dir": _ACTIVE_SESSION,
        "state": "issued",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)
    binding["permit_path"] = path.resolve().as_posix()
    binding["permit_state"] = "issued"
    binding["state"] = "reopen_pending"
    save_node_binding(approach_root, binding)
    return path


def reopen_session(
    approach_root: Path,
    *,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> dict[str, Any]:
    """Bind the session and issue its reopen permit."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    if shell["macro_state"] != "Session":
        raise ValueError(
            f"reopen requires macro_state=Session, got {shell['macro_state']!r}"
        )
    transaction = build_reopen(
        transaction_id=new_transaction_id(),
        state="preparing",
        previous={
            "macro_state": shell["macro_state"],
            "active_session": _active_session_name(root),
        },
    )
    save_reopen(root, transaction)
    binding = _start_binding(root, operation="reopen")
    try:
        result = _bind_session(
            root,
            project_root=project_root,
            cycle_id=cycle_id,
            constraints_path=constraints_path,
            binding=binding,
        )
        shell = load_shell(root)
        shell["macro_state"] = "Reopen"
        save_shell(root, shell)
        permit_path = _issue_reopen_permit(root, binding, cycle_id)
    except (FileNotFoundError, ValueError, OSError):
        transaction["state"] = "failed"
        save_reopen(root, transaction)
        raise
    transaction["state"] = "reopen_pending"
    save_reopen(root, transaction)
    return {
        "ok": True,
        "command": "reopen",
        "transaction_id": transaction["transaction_id"],
        "binding_id": binding["binding_id"],
        "permit_path": permit_path.resolve().as_posix(),
        "context_docs": result["decision"]["context_docs"],
        "context_snapshot": result["context_snapshot"],
        "shell": shell,
        "next_steps": {
            "require": [
                f"DEC_REOPEN --permit {permit_path.resolve().as_posix()}",
                "GATE_CONTROL resolve-context",
                "load context_docs",
                "declare session switched",
            ]
        },
    }


def complete_reopen(
    approach_root: Path,
    *,
    transaction_id: str,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> dict[str, Any]:
    """Close reopen after its permit-backed decision repair completes."""
    del project_root, cycle_id, constraints_path
    root = Path(approach_root).resolve()
    transaction = load_reopen(root)
    if transaction["transaction_id"] != str(transaction_id).strip():
        raise ValueError("complete-reopen transaction-id does not match")
    if transaction["state"] != "reopen_pending":
        raise ValueError(
            "complete-reopen requires reopen_pending transaction, "
            f"got {transaction['state']!r}"
        )
    binding = load_node_binding(root)
    if binding["state"] != "reopen_pending":
        raise ValueError("complete-reopen requires a pending session binding")
    permit_path = Path(str(binding.get("permit_path") or ""))
    if not permit_path.is_file():
        raise ValueError(f"complete-reopen permit missing: {permit_path}")
    permit = json.loads(permit_path.read_text(encoding="utf-8"))
    if (
        not isinstance(permit, dict)
        or permit.get("binding_id") != binding["binding_id"]
        or permit.get("state") != "consumed"
    ):
        raise ValueError("complete-reopen requires matching consumed permit")
    if _active_session_name(root) != _ACTIVE_SESSION:
        raise ValueError("complete-reopen requires the Active Session to remain this session")
    state = _parse_session_state_current(root / _SESSION_STATE)
    if state is None or state == "Frozen":
        raise ValueError("complete-reopen requires the session to be non-Frozen")
    shell = load_shell(root)
    if shell["macro_state"] != "Reopen":
        raise ValueError(
            f"complete-reopen requires macro_state=Reopen, got {shell['macro_state']!r}"
        )
    shell["macro_state"] = "Session"
    save_shell(root, shell)
    binding["state"] = "bound"
    binding["permit_state"] = "consumed"
    save_node_binding(root, binding)
    transaction["state"] = "repaired"
    save_reopen(root, transaction)
    return {
        "ok": True,
        "command": "complete-reopen",
        "transaction_id": transaction["transaction_id"],
        "state": transaction["state"],
        "shell": shell,
    }


def _restore_previous_binding(
    approach_root: Path,
    binding: dict[str, Any],
    *,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> None:
    previous = binding["previous"]
    if previous.get("active_session") == _ACTIVE_SESSION:
        session_dir = Path(approach_root).resolve()
        snapshot = resolve_context.write_resolved_context(
            Path(project_root).resolve(),
            str(cycle_id).strip(),
            Path(constraints_path).resolve(),
            session_dir=session_dir,
            binding_id=binding["binding_id"],
        )
        bind_session(
            Path(project_root).resolve(),
            str(cycle_id).strip(),
            session_dir=session_dir,
            resolved_context_path=snapshot,
            mode="existing",
            constraints_path=Path(constraints_path).resolve(),
        )


def recover_binding(
    approach_root: Path,
    *,
    action: str,
    project_root: Path,
    cycle_id: str,
    constraints_path: Path,
) -> dict[str, Any]:
    """Recover a paused session binding by compensation or explicit cancellation."""
    root = Path(approach_root).resolve()
    binding = load_node_binding(root)
    requested = str(action).strip()
    if requested not in _RECOVER_ACTIONS:
        raise ValueError("recover-binding action must be compensate-active|cancel")
    _restore_previous_binding(
        root,
        binding,
        project_root=project_root,
        cycle_id=cycle_id,
        constraints_path=constraints_path,
    )
    path = node_binding_path(root)
    path.unlink(missing_ok=True)
    return {
        "ok": True,
        "command": "recover-binding",
        "action": requested,
        "binding_id": binding["binding_id"],
        "binding_cleared": True,
    }


def enter_package_ready(approach_root: Path) -> dict[str, Any]:
    """Session Completed → PackageReady."""
    shell = load_shell(approach_root)
    if shell["macro_state"] != "Session":
        raise ValueError(
            f"enter_package_ready requires Session, got {shell['macro_state']!r}"
        )
    if not _session_completed(approach_root):
        raise ValueError("enter_package_ready blocked: session is not Completed")
    shell["macro_state"] = "PackageReady"
    save_shell(approach_root, shell)
    return shell


def _restore_file(path: Path, previous: bytes | None) -> None:
    if previous is None:
        path.unlink(missing_ok=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(previous)


def _write_decision_package(approach_root: Path) -> dict[str, Any]:
    root = Path(approach_root).resolve()
    ensure_approach_layout(root)
    package = build_decision_package(
        main={"decision_doc_path": "decision-doc.md"},
        status="draft",
    )
    save_decision_package(root, package)
    return package


def deliver(
    approach_root: Path,
    *,
    confirm: bool,
    cycle_id: str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Stage deliver at PackageReady; ensure decision-package; register refs."""
    root = Path(approach_root).resolve()
    shell = load_shell(root)
    if shell["macro_state"] != "PackageReady":
        raise ValueError(
            f"deliver requires macro_state=PackageReady, got {shell['macro_state']!r}"
        )
    if not confirm:
        raise ValueError("deliver blocked: human --confirm required")
    cid = str(cycle_id or "").strip()
    if not cid:
        raise ValueError("deliver requires --cycle-id")
    if project_root is None:
        raise ValueError("deliver requires --project-root")
    proj = Path(project_root).resolve()

    decision_pkg_path = decision_package_path(root)
    if not decision_pkg_path.is_file():
        _write_decision_package(root)
    load_decision_package(decision_pkg_path)

    refs_path = delivered_refs_file_path(cid, proj)
    refs_before = refs_path.read_bytes() if refs_path.is_file() else None
    residual_source = source_package_path(root)
    source = str(shell_path(root).resolve())
    try:
        record_delivered_ref(
            cid,
            proj,
            delivered_type="lulu-approach",
            path=str(decision_pkg_path.resolve()),
            artifact="decision-package",
            revision=1,
            profile_id="lulu-approach",
            source_workflow_state=source,
        )
        residual_source.unlink(missing_ok=True)
    except Exception:
        _restore_file(refs_path, refs_before)
        raise
    cycle_type = "topic" if cid.startswith("topic-") else "feature"
    return {
        "ok": True,
        "macro_state": "PackageReady",
        "delivered": True,
        "decision_package": str(decision_pkg_path.resolve()),
        "source_workflow_state": source,
        "next_steps": next_steps_for_stage("lulu-approach", cycle_type),
    }


def confirm_seal(
    approach_root: Path,
    *,
    confirm: bool,
    cycle_id: str | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Deprecated alias for ``deliver``."""
    return deliver(
        approach_root,
        confirm=confirm,
        cycle_id=cycle_id,
        project_root=project_root,
    )


def _emit_ok(payload: dict[str, Any]) -> int:
    out = dict(payload)
    out.setdefault("ok", True)
    print(json.dumps(out, ensure_ascii=False))
    return 0


def _emit_err(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="approach_shell_control.py",
        description="Approach outer-shell control (Session → PackageReady).",
    )
    p.add_argument("--approach-root", required=True, type=Path)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init-shell", help="Create the approach root and session shell")

    def _session_parser(name: str, help_text: str) -> None:
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--project-root", type=Path)
        command.add_argument("--cycle-id", required=True)
        command.add_argument("--constraints", required=True, type=Path)

    _session_parser("enter", "Bind the session and the Active Session")
    _session_parser("reopen", "Bind the session and issue a reopen permit")

    done = sub.add_parser(
        "complete-reopen",
        help="Finish a consumed reopen permit after RS",
    )
    done.add_argument("--transaction-id", required=True)
    done.add_argument("--project-root", type=Path)
    done.add_argument("--cycle-id", required=True)
    done.add_argument("--constraints", required=True, type=Path)

    recover = sub.add_parser(
        "recover-binding",
        help="Recover a paused session binding",
    )
    recover.add_argument("--action", required=True, choices=sorted(_RECOVER_ACTIONS))
    recover.add_argument("--project-root", type=Path)
    recover.add_argument("--cycle-id", required=True)
    recover.add_argument("--constraints", required=True, type=Path)

    sub.add_parser("enter-package-ready", help="Session Completed → PackageReady")
    for cmd_name, help_text in (
        ("deliver", "Stage deliver + delivered-refs (decision-package)"),
        ("confirm-seal", "Deprecated alias for deliver"),
    ):
        seal = sub.add_parser(cmd_name, help=help_text)
        seal.add_argument("--confirm", action="store_true")
        seal.add_argument("--cycle-id", required=True)
        seal.add_argument("--project-root", type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    apply_project_root_arg(args)
    root = Path(args.approach_root).resolve()
    try:
        if args.command == "init-shell":
            return _emit_ok({"shell": init_shell(root)})
        if args.command == "enter":
            return _emit_ok(
                enter_session(
                    root,
                    project_root=Path(args.project_root),
                    cycle_id=args.cycle_id,
                    constraints_path=Path(args.constraints),
                )
            )
        if args.command == "reopen":
            return _emit_ok(
                reopen_session(
                    root,
                    project_root=Path(args.project_root),
                    cycle_id=args.cycle_id,
                    constraints_path=Path(args.constraints),
                )
            )
        if args.command == "complete-reopen":
            return _emit_ok(
                complete_reopen(
                    root,
                    transaction_id=args.transaction_id,
                    project_root=Path(args.project_root),
                    cycle_id=args.cycle_id,
                    constraints_path=Path(args.constraints),
                )
            )
        if args.command == "recover-binding":
            return _emit_ok(
                recover_binding(
                    root,
                    action=args.action,
                    project_root=Path(args.project_root),
                    cycle_id=args.cycle_id,
                    constraints_path=Path(args.constraints),
                )
            )
        if args.command == "enter-package-ready":
            return _emit_ok({"shell": enter_package_ready(root)})
        if args.command in {"deliver", "confirm-seal"}:
            return _emit_ok(
                deliver(
                    root,
                    confirm=bool(args.confirm),
                    cycle_id=args.cycle_id,
                    project_root=Path(args.project_root),
                )
            )
    except (ValueError, FileNotFoundError, OSError, RuntimeError) as exc:
        return _emit_err(str(exc))
    return _emit_err(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    raise SystemExit(main())
