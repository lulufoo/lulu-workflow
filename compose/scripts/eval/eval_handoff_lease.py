#!/usr/bin/env python3
"""Lease-scoped staging and EvalTarget publication for Compose → Eval handoff.

Every Eval write lands in ``execution/.eval-staging/<lease_id>/`` first; the
lease binds the current ``execution_fingerprint`` and ``eval_run_id`` so stale
Eval runs cannot publish after the execution moved on.
"""

from __future__ import annotations

import hashlib
import json
import os
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

from compose_session import workflow_state_path  # noqa: E402
from execution_checks import EVAL_STAGING_DIR, load_eval_run  # noqa: E402
from execution_state_schema import (  # noqa: E402
    execution_dir,
    execution_fingerprint,
    load_execution_state,
)
from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID  # noqa: E402
from workflow_profile_paths import document_path  # noqa: E402

LEASE_META = "lease.json"
CMD_COMMIT_TARGET = "commit-eval-target"
CMD_RESTORE_TARGET = "restore-eval-target"


def failure(command: str, error: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "command": command, "error": error}
    payload.update(extra)
    return payload


def success(command: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "command": command}
    payload.update(extra)
    return payload


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_replace(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dest)


def bind_execution(
    revision_dir: Path,
    *,
    command: str,
    require_evaluating: bool,
) -> tuple[Path, str] | dict[str, Any]:
    """Return ``(execution_dir, execution_fingerprint)`` or a failure payload."""
    try:
        state = load_execution_state(revision_dir)
    except (OSError, ValueError, FileNotFoundError) as exc:
        return failure(command, str(exc))
    if require_evaluating and state["state"] != "Evaluating":
        return failure(
            command,
            f"execution state is {state['state']!r}, expected 'Evaluating'",
            state=state["state"],
        )
    return execution_dir(revision_dir), execution_fingerprint(state)


def current_eval_run(
    execution_dir_path: Path,
    *,
    fingerprint: str,
    command: str,
) -> dict[str, str] | dict[str, Any]:
    """Return the eval run bound to ``fingerprint`` or a failure payload."""
    meta = load_eval_run(execution_dir_path)
    if meta is None:
        return failure(command, "missing eval_run_id; run enter-evaluating first")
    run_id = str(meta.get("eval_run_id", "")).strip()
    digest = str(meta.get("execution_fingerprint", "")).strip()
    if not run_id or not digest:
        return failure(command, "invalid _eval_run.json")
    if digest != fingerprint:
        return failure(command, "stale eval_run_id: execution fingerprint mismatch")
    return {"eval_run_id": run_id, "execution_fingerprint": digest}


def create_lease(
    execution_dir_path: Path,
    *,
    fingerprint: str,
    eval_run_id: str,
) -> dict[str, str]:
    lease_id = uuid.uuid4().hex
    staging = execution_dir_path / EVAL_STAGING_DIR / lease_id
    staging.mkdir(parents=True, exist_ok=True)
    meta = {
        "lease_id": lease_id,
        "execution_fingerprint": fingerprint,
        "eval_run_id": eval_run_id,
    }
    (staging / LEASE_META).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {"lease_id": lease_id, "write_staging_dir": staging.resolve().as_posix()}


def load_lease_meta(staging_dir: Path) -> dict[str, Any]:
    meta_path = staging_dir / LEASE_META
    if not meta_path.is_file():
        raise ValueError(f"lease meta missing: {meta_path}")
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("lease meta must be an object")
    return data


def _active_target_and_staging(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str,
    command: str,
) -> tuple[Path, Path, str] | dict[str, Any]:
    root = project_root.resolve()
    ws_path = workflow_state_path(cycle_id, root, profile_id)
    if not ws_path.is_file():
        return failure(command, "workflow-state.md not found")
    bound = bind_execution(ws_path.parent.resolve(), command=command, require_evaluating=True)
    if isinstance(bound, dict):
        return bound
    exec_dir, fingerprint = bound
    active_doc = load_active_doc_from_cycle(cycle_id, root, profile_id=profile_id)
    target = (root / document_path(cycle_id, active_doc, profile_id, root)).resolve()
    return target, (exec_dir / EVAL_STAGING_DIR).resolve(), fingerprint


def _current_lease_dir(
    staging_root: Path,
    *,
    lease_id: str,
    fingerprint: str,
    command: str,
) -> Path | dict[str, Any]:
    if not lease_id:
        return failure(command, "lease_id is required")
    lease_dir = (staging_root / lease_id).resolve()
    try:
        lease_dir.relative_to(staging_root)
    except ValueError:
        return failure(command, "lease_id resolves outside Eval staging")
    if not lease_dir.is_dir():
        return failure(command, f"lease staging missing: {lease_dir}")
    try:
        meta = load_lease_meta(lease_dir)
    except ValueError as exc:
        return failure(command, str(exc))
    if str(meta.get("execution_fingerprint")) != fingerprint:
        return failure(command, "stale lease: execution changed")
    return lease_dir


def _lease_scoped_path(lease_dir: Path, candidate: Path, *, command: str) -> Path | dict[str, Any]:
    resolved = candidate.resolve()
    try:
        resolved.relative_to(lease_dir)
    except ValueError:
        return failure(command, "staged target is outside Eval lease staging")
    if not resolved.is_file():
        return failure(command, f"staged target missing: {resolved}")
    return resolved


def _publish(target: Path, source: Path, *, command: str, verb: str) -> dict[str, Any] | None:
    try:
        replacement = target.with_name(target.name + ".eval-remediation.tmp")
        shutil.copy2(source, replacement)
        atomic_replace(replacement, target)
    except OSError as exc:
        return failure(command, f"target {verb} failed: {exc}")
    return None


def read_eval_target_digest(*, target_path: Path) -> str:
    """Return the live SHA-256 digest of an EvalTarget file."""
    return file_digest(Path(target_path))


def commit_eval_target(
    cycle_id: str,
    project_root: Path,
    *,
    staged_target_path: Path,
    base_digest: str,
    lease_id: str,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Publish a verified replacement of the active stage document."""
    resolved = _active_target_and_staging(
        cycle_id, project_root, profile_id=profile_id, command=CMD_COMMIT_TARGET
    )
    if isinstance(resolved, dict):
        return resolved
    target, staging_root, fingerprint = resolved
    lease_dir = _current_lease_dir(
        staging_root, lease_id=lease_id, fingerprint=fingerprint, command=CMD_COMMIT_TARGET
    )
    if isinstance(lease_dir, dict):
        return lease_dir
    staged = _lease_scoped_path(lease_dir, staged_target_path, command=CMD_COMMIT_TARGET)
    if isinstance(staged, dict):
        return staged
    if not target.is_file():
        return failure(CMD_COMMIT_TARGET, f"target document missing: {target}")
    if file_digest(target) != base_digest:
        return failure(CMD_COMMIT_TARGET, "target base digest mismatch")
    error = _publish(target, staged, command=CMD_COMMIT_TARGET, verb="publish")
    if error:
        return error
    return success(
        CMD_COMMIT_TARGET,
        target_path=target.as_posix(),
        target_digest=file_digest(target),
    )


def restore_eval_target(
    cycle_id: str,
    project_root: Path,
    *,
    snapshot_path: Path,
    expected_current_digest: str,
    lease_id: str,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Restore an Eval snapshot when a later Eval-owned publication fails."""
    resolved = _active_target_and_staging(
        cycle_id, project_root, profile_id=profile_id, command=CMD_RESTORE_TARGET
    )
    if isinstance(resolved, dict):
        return resolved
    target, staging_root, fingerprint = resolved
    lease_dir = _current_lease_dir(
        staging_root, lease_id=lease_id, fingerprint=fingerprint, command=CMD_RESTORE_TARGET
    )
    if isinstance(lease_dir, dict):
        return lease_dir
    snapshot = _lease_scoped_path(lease_dir, snapshot_path, command=CMD_RESTORE_TARGET)
    if isinstance(snapshot, dict):
        return snapshot
    if not target.is_file() or file_digest(target) != expected_current_digest:
        return failure(CMD_RESTORE_TARGET, "target changed before rollback")
    error = _publish(target, snapshot, command=CMD_RESTORE_TARGET, verb="rollback")
    if error:
        return error
    return success(CMD_RESTORE_TARGET, target_path=target.as_posix())
