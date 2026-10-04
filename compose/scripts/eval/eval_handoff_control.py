#!/usr/bin/env python3
"""Compose → Eval handoff control.

Subcommands:
    request-handoff       Build EvalHandoff for the current execution
    commit-artifacts      Atomically publish staged review + optional state patch
    discard-staging       Drop lease-private staging for a lease_id
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

_CORE = Path(__file__).resolve().parent
_SCRIPTS = _CORE.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from project_root import apply_project_root_arg  # noqa: E402

from compose_session import workflow_state_path  # noqa: E402
from eval_handoff_lease import (  # noqa: E402
    bind_execution,
    commit_eval_target,
    create_lease,
    current_eval_run,
    read_eval_target_digest,
    restore_eval_target,
)
from eval_handoff_publish import (  # noqa: E402
    commit_artifacts,
    commit_evaluate_state,
    discard_staging_for_cycle,
    resolve_evaluate_state_abs,
)
from compose_eval_handoff_schema import validate_eval_handoff  # noqa: E402
from resolved_refs_schema import frozen_delivered_path_by_type  # noqa: E402
from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import detect_cycle_type  # noqa: E402
from workflow_paths import (  # noqa: E402
    DEFAULT_COMPOSE_PROFILE_ID,
    WORKFLOW_ROOT,
    load_profile,
    resolve_profile_id,
    shell_path,
)
from workflow_profile_paths import (  # noqa: E402
    document_path,
    execution_eval_round_dir,
    execution_evaluate_state_path,
)
from workflow_state_schema import load_workflow_state  # noqa: E402

_CMD_REQUEST = "request-handoff"
_CMD_COMMIT = "commit-artifacts"
_CMD_COMMIT_STATE = "commit-evaluate-state"
_CMD_DISCARD = "discard-staging"


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _failure(command: str, error: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "command": command, "error": error}
    payload.update(extra)
    return payload


def _success(command: str, **extra: Any) -> dict[str, Any]:
    return {"ok": True, "command": command, **extra}


def _read_eval_status(path: Path) -> str:
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("eval_status:"):
            return line.split(":", 1)[1].strip()
    return ""


def _read_evaluate_round_field(path: Path) -> int | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("evaluate_round:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def _allocate_round(execution_dir_path: Path) -> int:
    es_path = execution_dir_path / "evaluate-state.md"
    if not es_path.is_file():
        return 1
    status = _read_eval_status(es_path)
    current = _read_evaluate_round_field(es_path) or 1
    if status in {"done", "abandoned"}:
        return current + 1
    return current if current >= 1 else 1


def _build_adapter_ref(profile: dict[str, Any]) -> dict[str, str]:
    from compose_eval_envelope import OUTER_ADAPTER_MODULE, build_compose_eval_envelope  # noqa: WPS433

    envelope = build_compose_eval_envelope(profile)
    module_path = (WORKFLOW_ROOT / OUTER_ADAPTER_MODULE).resolve()
    if not module_path.is_file():
        raise ValueError(f"eval.adapter_module not found: {module_path.as_posix()}")
    workflow_id = str(envelope["workflow_id"])
    return {
        "workflow_id": workflow_id,
        "adapter_module": module_path.as_posix(),
        "adapter_class": str(envelope["adapter_class"]),
        "dimension_defs_dir": shell_path(profile, "dimension_defs_dir").resolve().as_posix(),
        "framework_section": str(profile.get("framework_section", "")).strip() or workflow_id,
    }


def _bind_or_fail(
    revision_dir: Path, *, command: str, require_evaluating: bool
) -> tuple[Path, str] | dict[str, Any]:
    return bind_execution(
        revision_dir, command=command, require_evaluating=require_evaluating
    )


def request_handoff(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    require_evaluating: bool = True,
) -> dict[str, Any]:
    """Build a fresh EvalHandoff for the current execution."""
    root = project_root.resolve()
    try:
        profile = load_profile(profile_id, project_root=root, cycle_id=cycle_id)
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _failure(_CMD_REQUEST, str(exc))
    if not (profile.get("eval") or {}).get("enabled", False):
        return _failure(_CMD_REQUEST, "profile.eval.enabled is false")
    try:
        adapter = _build_adapter_ref(profile)
    except ValueError as exc:
        return _failure(_CMD_REQUEST, str(exc))
    ws_path = workflow_state_path(cycle_id, root, profile_id)
    if not ws_path.is_file():
        return _failure(_CMD_REQUEST, f"workflow-state.md not found: {ws_path}")
    try:
        state = load_workflow_state(ws_path)
    except ValueError as exc:
        return _failure(_CMD_REQUEST, str(exc))
    if state.get("current_state") != "Working":
        return _failure(
            _CMD_REQUEST,
            f"current_state is {state.get('current_state')!r}, expected 'Working'",
        )
    revision_dir = ws_path.parent.resolve()
    bound = _bind_or_fail(
        revision_dir, command=_CMD_REQUEST, require_evaluating=require_evaluating
    )
    if isinstance(bound, dict):
        return bound
    exec_dir, fingerprint = bound
    exec_dir.mkdir(parents=True, exist_ok=True)
    eval_run = current_eval_run(exec_dir, fingerprint=fingerprint, command=_CMD_REQUEST)
    if eval_run.get("ok") is False:
        if require_evaluating:
            return eval_run
        eval_run = {"eval_run_id": uuid.uuid4().hex, "execution_fingerprint": fingerprint}
    run_id = str(eval_run["eval_run_id"])
    active_doc = load_active_doc_from_cycle(cycle_id, root, profile_id=profile_id)
    evaluate_round = _allocate_round(exec_dir)
    lease = create_lease(exec_dir, fingerprint=fingerprint, eval_run_id=run_id)
    context = {
        "cycle_id": cycle_id,
        "profile_id": profile_id,
        "execution_fingerprint": fingerprint,
        "eval_run_id": run_id,
        "evaluate_round": evaluate_round,
        "revision_dir": revision_dir.as_posix(),
        "execution_dir": exec_dir.as_posix(),
        "compose_doc": (root / document_path(cycle_id, active_doc, profile_id, root)).resolve().as_posix(),
        "evaluate_state_path": (root / execution_evaluate_state_path(cycle_id, active_doc, profile_id, root)).resolve().as_posix(),
        "evaluate_dir": (root / execution_eval_round_dir(cycle_id, active_doc, evaluate_round, profile_id, root)).resolve().as_posix(),
        "write_staging_dir": lease["write_staging_dir"],
        "lease_id": lease["lease_id"],
        "policy_context": {
            "mode": state.get("mode", "tech"),
            "cycle_type": detect_cycle_type(cycle_id),
            "upstream_baseline_ref": frozen_delivered_path_by_type(revision_dir, "lulu-spec") or "",
            "eval_capability": str((profile.get("eval") or {}).get("eval_capability") or "").strip(),
        },
    }
    handoff = {"adapter": adapter, "context": context}
    errors = validate_eval_handoff(handoff)
    if errors:
        shutil.rmtree(lease["write_staging_dir"], ignore_errors=True)
        return _failure(_CMD_REQUEST, "; ".join(errors))
    return _success(_CMD_REQUEST, handoff=handoff)


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compose EvalHandoff control")
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    sub = parser.add_subparsers(dest="command", required=True)
    req = sub.add_parser(_CMD_REQUEST)
    req.add_argument("--allow-non-evaluating", action="store_true")
    commit = sub.add_parser(_CMD_COMMIT)
    commit.add_argument("--manifest-json", required=True)
    commit_state = sub.add_parser(_CMD_COMMIT_STATE)
    commit_state.add_argument("--staged-state", type=Path, required=True)
    commit_state.add_argument("--set-phase-evaluating", action="store_true")
    commit_state.add_argument("--previous-done-required", action="store_true")
    discard = sub.add_parser(_CMD_DISCARD)
    discard.add_argument("--lease-id", required=True)
    args = parser.parse_args(argv)
    apply_project_root_arg(args)
    root = args.project_root.resolve()
    cycle_id = str(args.cycle_id).strip()
    try:
        profile_id = resolve_profile_id(project_root=root, cycle_id=cycle_id)
    except (ValueError, FileNotFoundError, OSError) as exc:
        return _emit(_failure(args.command, str(exc)))
    if args.command == _CMD_REQUEST:
        return _emit(request_handoff(cycle_id, root, profile_id=profile_id, require_evaluating=not args.allow_non_evaluating))
    if args.command == _CMD_COMMIT:
        try:
            manifest = json.loads(args.manifest_json)
        except json.JSONDecodeError as exc:
            return _emit(_failure(_CMD_COMMIT, f"invalid manifest JSON: {exc}"))
        return _emit(commit_artifacts(cycle_id, root, manifest=manifest, profile_id=profile_id))
    if args.command == _CMD_COMMIT_STATE:
        return _emit(commit_evaluate_state(cycle_id, root, staged_state_path=args.staged_state, profile_id=profile_id, set_phase_evaluating=bool(args.set_phase_evaluating), previous_done_required=bool(args.previous_done_required)))
    if args.command == _CMD_DISCARD:
        return _emit(discard_staging_for_cycle(cycle_id, root, lease_id=str(args.lease_id), profile_id=profile_id))
    return _emit(_failure(str(args.command), f"unknown command: {args.command}"))


if __name__ == "__main__":
    raise SystemExit(_cli())
