#!/usr/bin/env python3
"""Publish and discard helpers for Compose → Eval handoff."""

from __future__ import annotations

import shutil
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
from eval_handoff_lease import (  # noqa: E402
    atomic_replace,
    bind_execution,
    current_eval_run,
    file_digest,
    load_lease_meta,
)
from compose_eval_handoff_schema import validate_artifact_manifest  # noqa: E402
from execution_checks import EVAL_STAGING_DIR  # noqa: E402
from execution_eval_entry import enter_evaluating_state  # noqa: E402
from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID  # noqa: E402
from workflow_profile_paths import execution_evaluate_state_path  # noqa: E402

CMD_COMMIT = "commit-artifacts"
CMD_COMMIT_STATE = "commit-evaluate-state"
CMD_DISCARD = "discard-staging"


def _failure(command: str, error: str, **extra: Any) -> dict[str, Any]:
    return {"ok": False, "command": command, "error": error, **extra}


def _success(command: str, **extra: Any) -> dict[str, Any]:
    return {"ok": True, "command": command, **extra}


def _read_eval_status(path: Path) -> str:
    if not path.is_file():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("eval_status:"):
            return line.split(":", 1)[1].strip()
    return ""


def discard_staging_for_cycle(
    cycle_id: str,
    project_root: Path,
    *,
    lease_id: str,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    root = project_root.resolve()
    ws_path = workflow_state_path(cycle_id, root, profile_id)
    if not ws_path.is_file():
        return _failure(CMD_DISCARD, "workflow-state.md not found")
    bound = bind_execution(
        ws_path.parent.resolve(), command=CMD_DISCARD, require_evaluating=False
    )
    if isinstance(bound, dict):
        return bound
    staging = (bound[0] / EVAL_STAGING_DIR / lease_id).resolve()
    if staging.is_dir():
        shutil.rmtree(staging, ignore_errors=True)
    return _success(CMD_DISCARD, lease_id=lease_id)


def commit_artifacts(
    cycle_id: str,
    project_root: Path,
    *,
    manifest: dict[str, Any],
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    errors = validate_artifact_manifest(manifest)
    if errors:
        return _failure(CMD_COMMIT, "; ".join(errors))
    root = project_root.resolve()
    ws_path = workflow_state_path(cycle_id, root, profile_id)
    if not ws_path.is_file():
        return _failure(CMD_COMMIT, "workflow-state.md not found")
    bound = bind_execution(
        ws_path.parent.resolve(), command=CMD_COMMIT, require_evaluating=True
    )
    if isinstance(bound, dict):
        return bound
    exec_dir, fingerprint = bound
    if fingerprint != str(manifest["execution_fingerprint"]):
        return _failure(CMD_COMMIT, "stale handoff: execution_fingerprint mismatch")
    eval_run = current_eval_run(exec_dir, fingerprint=fingerprint, command=CMD_COMMIT)
    if eval_run.get("ok") is False:
        return eval_run
    if str(eval_run["eval_run_id"]) != str(manifest["eval_run_id"]):
        return _failure(CMD_COMMIT, "stale handoff: eval_run_id mismatch")
    staging = (exec_dir / EVAL_STAGING_DIR / str(manifest["lease_id"])).resolve()
    if not staging.is_dir():
        return _failure(CMD_COMMIT, f"staging dir missing: {staging}")
    try:
        meta = load_lease_meta(staging)
    except ValueError as exc:
        return _failure(CMD_COMMIT, str(exc))
    if str(meta.get("execution_fingerprint")) != fingerprint:
        shutil.rmtree(staging, ignore_errors=True)
        return _failure(CMD_COMMIT, "stale lease: execution changed; staging discarded")
    staged = staging / str(manifest["staged_relative_path"])
    if not staged.is_file():
        return _failure(CMD_COMMIT, f"staged artifact missing: {staged}")
    if file_digest(staged) != str(manifest["artifact_digest"]):
        return _failure(CMD_COMMIT, "artifact digest mismatch")
    evaluate_round = int(manifest["evaluate_round"])
    final_path = exec_dir / f"evaluate{evaluate_round}" / str(manifest["final_relative_path"])
    tmp_publish = final_path.with_name(final_path.name + ".tmp")
    try:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged, tmp_publish)
        atomic_replace(tmp_publish, final_path)
    except OSError as exc:
        if tmp_publish.exists():
            tmp_publish.unlink(missing_ok=True)
        return _failure(CMD_COMMIT, f"publish failed: {exc}")
    shutil.rmtree(staging, ignore_errors=True)
    return _success(CMD_COMMIT, published_path=final_path.as_posix(), evaluate_round=evaluate_round)


def commit_evaluate_state(
    cycle_id: str,
    project_root: Path,
    *,
    staged_state_path: Path,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    set_phase_evaluating: bool = False,
    previous_done_required: bool = False,
) -> dict[str, Any]:
    root = project_root.resolve()
    staged = Path(staged_state_path).resolve()
    if not staged.is_file():
        return _failure(CMD_COMMIT_STATE, f"staged state missing: {staged}")
    ws_path = workflow_state_path(cycle_id, root, profile_id)
    if not ws_path.is_file():
        return _failure(CMD_COMMIT_STATE, "workflow-state.md not found")
    bound = bind_execution(
        ws_path.parent.resolve(),
        command=CMD_COMMIT_STATE,
        require_evaluating=not set_phase_evaluating,
    )
    if isinstance(bound, dict):
        return bound
    active_doc = load_active_doc_from_cycle(cycle_id, root, profile_id=profile_id)
    formal = (
        root / execution_evaluate_state_path(cycle_id, active_doc, profile_id, root)
    ).resolve()
    if previous_done_required:
        if not formal.is_file():
            return _failure(CMD_COMMIT_STATE, "previous evaluate-state.md missing")
        if _read_eval_status(formal) != "done":
            return _failure(CMD_COMMIT_STATE, "previous evaluate-state.md is not done")
    backup = formal.with_suffix(formal.suffix + ".bak") if formal.is_file() else None
    published = False
    try:
        if backup is not None:
            shutil.copy2(formal, backup)
        atomic_replace(staged, formal)
        published = True
        if set_phase_evaluating:
            transition = enter_evaluating_state(cycle_id, root, profile_id=profile_id)
            if not transition.get("ok"):
                raise ValueError(str(transition.get("error") or "failed to enter Evaluating"))
    except (OSError, ValueError) as exc:
        if published:
            if backup is not None and backup.is_file():
                shutil.copy2(backup, formal)
            else:
                formal.unlink(missing_ok=True)
        return _failure(CMD_COMMIT_STATE, str(exc))
    finally:
        if backup is not None and backup.is_file():
            backup.unlink(missing_ok=True)
    return _success(CMD_COMMIT_STATE, evaluate_state_path=formal.as_posix())


def resolve_evaluate_state_abs(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    root = project_root.resolve()
    active_doc = load_active_doc_from_cycle(cycle_id, root, profile_id=profile_id)
    return (
        root / execution_evaluate_state_path(cycle_id, active_doc, profile_id, root)
    ).resolve()
