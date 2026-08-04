#!/usr/bin/env python3
"""Compose → Eval handoff control.

Subcommands:
    request-handoff       Build EvalHandoff for the current focus L
    commit-artifacts      Atomically publish staged review + optional state patch
    discard-staging       Drop lease-private staging for a lease_id

CLI:
    python3 eval_handoff_control.py --cycle-id <id> --project-root <root>
        --profile <profile_id> <subcommand> [...]
"""

from __future__ import annotations

import argparse
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
from discussion_pointer_schema import (  # noqa: E402
    DISCUSSION_POINTER_FILENAME,
    load_discussion_pointer,
)
from eval_handoff_schema import (  # noqa: E402
    pointer_fingerprint,
    validate_artifact_manifest,
    validate_eval_handoff,
)
from resolved_refs_schema import frozen_delivered_path_by_type  # noqa: E402
from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import detect_cycle_type  # noqa: E402
from workflow_paths import (  # noqa: E402
    DEFAULT_COMPOSE_PROFILE_ID,
    WORKFLOW_ROOT,
    compose_profile_path,
    load_profile,
    load_profile_json,
    shell_path,
)
from workflow_profile_paths import (  # noqa: E402
    document_path,
    eval_layout_for_revision,
    eval_round_dir_for_layout,
    evaluate_state_path_for_layout,
)
from workflow_state_schema import load_workflow_state  # noqa: E402

_CMD_REQUEST = "request-handoff"
_CMD_COMMIT = "commit-artifacts"
_CMD_COMMIT_STATE = "commit-evaluate-state"
_CMD_COMMIT_TARGET = "commit-remediation-target"
_CMD_RESTORE_TARGET = "restore-remediation-target"
_CMD_DISCARD = "discard-staging"
_STAGING_ROOT = ".eval-staging"
_LEASE_META = "lease.json"


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _failure(command: str, error: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "command": command, "error": error}
    payload.update(extra)
    return payload


def _success(command: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "command": command}
    payload.update(extra)
    return payload


def _read_eval_status(path: Path) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("eval_status:"):
            return line.split(":", 1)[1].strip()
    return ""


def _read_evaluate_round_field(path: Path) -> int | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("evaluate_round:"):
            raw = line.split(":", 1)[1].strip()
            try:
                return int(raw)
            except ValueError:
                return None
    return None


def _build_adapter_ref(profile: dict[str, Any]) -> dict[str, str]:
    eval_cfg = profile.get("eval") or {}
    if not eval_cfg.get("enabled", False):
        raise ValueError("profile.eval.enabled is false")
    workflow_id = str(eval_cfg.get("workflow_id", "")).strip()
    adapter_module = str(eval_cfg.get("adapter_module", "")).strip()
    adapter_class = str(eval_cfg.get("adapter_class", "")).strip()
    if not workflow_id or not adapter_module or not adapter_class:
        raise ValueError("profile.eval missing workflow_id/adapter_module/adapter_class")
    module_path = Path(adapter_module)
    if not module_path.is_absolute():
        module_path = (WORKFLOW_ROOT / module_path).resolve()
    if not module_path.is_file():
        raise ValueError(f"eval.adapter_module not found: {module_path.as_posix()}")
    dim_dir = shell_path(profile, "dimension_defs_dir").resolve()
    framework_section = str(profile.get("framework_section", "")).strip() or workflow_id
    return {
        "workflow_id": workflow_id,
        "adapter_module": module_path.as_posix(),
        "adapter_class": adapter_class,
        "dimension_defs_dir": dim_dir.as_posix(),
        "framework_section": framework_section,
    }


def _allocate_per_l_round(slice_dir: Path) -> int:
    es_path = slice_dir / "evaluate-state.md"
    if not es_path.is_file():
        return 1
    status = _read_eval_status(es_path)
    current = _read_evaluate_round_field(es_path)
    if current is None:
        current = 1
    if status == "done":
        return current + 1
    if status == "active":
        return current
    if status == "abandoned":
        return current + 1
    return current if current >= 1 else 1


def _legacy_round_from_workflow(ws_path: Path, es_path: Path) -> int:
    state = load_workflow_state(ws_path)
    try:
        value = int(state.get("evaluate_round", "0"))
    except ValueError:
        value = 0
    if value < 1:
        value = 1
    status = _read_eval_status(es_path)
    if status == "done":
        return value + 1
    if status == "abandoned":
        return value + 1
    return value


def _create_lease(slice_dir: Path, *, fingerprint: str, focus_l: str) -> dict[str, str]:
    lease_id = uuid.uuid4().hex
    staging = slice_dir / _STAGING_ROOT / lease_id
    staging.mkdir(parents=True, exist_ok=True)
    meta = {
        "lease_id": lease_id,
        "pointer_fingerprint": fingerprint,
        "focus_l": focus_l,
    }
    (staging / _LEASE_META).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "lease_id": lease_id,
        "write_staging_dir": staging.resolve().as_posix(),
    }


def _load_lease_meta(staging_dir: Path) -> dict[str, Any]:
    meta_path = staging_dir / _LEASE_META
    if not meta_path.is_file():
        raise ValueError(f"lease meta missing: {meta_path}")
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("lease meta must be an object")
    return data


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_replace(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dest)


def request_handoff(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    require_evaluating: bool = True,
) -> dict[str, Any]:
    """Build a fresh EvalHandoff for the current focus L."""
    root = project_root.resolve()
    try:
        profile = load_profile(profile_id, project_root=root, cycle_id=cycle_id)
    except (OSError, ValueError, FileNotFoundError) as exc:
        # Tests / early sessions may only have authoring profile
        try:
            profile = load_profile_json(compose_profile_path(profile_id))
        except (OSError, ValueError, FileNotFoundError):
            return _failure(_CMD_REQUEST, str(exc))

    eval_cfg = profile.get("eval") or {}
    if not eval_cfg.get("enabled", False):
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
    pointer_path = revision_dir / DISCUSSION_POINTER_FILENAME
    if not pointer_path.is_file():
        return _failure(_CMD_REQUEST, "discussion-pointer.json not found")
    try:
        pointer = load_discussion_pointer(revision_dir)
    except (OSError, ValueError) as exc:
        return _failure(_CMD_REQUEST, str(exc))

    focus = str(pointer["focus"])
    cell = pointer["by_id"][focus]
    phase = str(cell.get("phase", ""))
    if require_evaluating and phase != "evaluating":
        return _failure(
            _CMD_REQUEST,
            f"focus {focus!r} phase is {phase!r}, expected 'evaluating'",
            focus_l=focus,
            phase=phase,
        )

    fingerprint = pointer_fingerprint(pointer)
    layout = eval_layout_for_revision(revision_dir)
    active_doc = load_active_doc_from_cycle(cycle_id, root, profile_id=profile_id)

    if layout == "legacy-root":
        slice_dir = revision_dir
        es_rel = evaluate_state_path_for_layout(
            cycle_id, active_doc, profile_id, root, layout="legacy-root", focus_l=focus
        )
        evaluate_round = _legacy_round_from_workflow(ws_path, root / es_rel)
        eval_rel = eval_round_dir_for_layout(
            cycle_id,
            active_doc,
            evaluate_round,
            profile_id,
            root,
            layout="legacy-root",
            focus_l=focus,
        )
    else:
        slice_dir = (revision_dir / focus).resolve()
        slice_dir.mkdir(parents=True, exist_ok=True)
        evaluate_round = _allocate_per_l_round(slice_dir)
        es_rel = evaluate_state_path_for_layout(
            cycle_id, active_doc, profile_id, root, layout="per-l", focus_l=focus
        )
        eval_rel = eval_round_dir_for_layout(
            cycle_id,
            active_doc,
            evaluate_round,
            profile_id,
            root,
            layout="per-l",
            focus_l=focus,
        )

    compose_doc = (root / document_path(cycle_id, active_doc, profile_id, root)).resolve()
    es_path = (root / es_rel).resolve()
    evaluate_dir = (root / eval_rel).resolve()
    lease = _create_lease(slice_dir, fingerprint=fingerprint, focus_l=focus)

    upstream = frozen_delivered_path_by_type(revision_dir, "lulu-spec")
    context = {
        "cycle_id": cycle_id,
        "profile_id": profile_id,
        "focus_l": focus,
        "pointer_fingerprint": fingerprint,
        "evaluate_round": evaluate_round,
        "revision_dir": revision_dir.as_posix(),
        "slice_dir": slice_dir.as_posix(),
        "compose_doc": compose_doc.as_posix(),
        "evaluate_state_path": es_path.as_posix(),
        "evaluate_dir": evaluate_dir.as_posix(),
        "write_staging_dir": lease["write_staging_dir"],
        "lease_id": lease["lease_id"],
        "layout": layout,
        "policy_context": {
            "mode": state.get("mode", "tech"),
            "cycle_type": detect_cycle_type(cycle_id),
            "upstream_baseline_ref": upstream or "",
        },
    }
    handoff = {"adapter": adapter, "context": context}
    errors = validate_eval_handoff(handoff)
    if errors:
        shutil.rmtree(lease["write_staging_dir"], ignore_errors=True)
        return _failure(_CMD_REQUEST, "; ".join(errors))

    return _success(_CMD_REQUEST, handoff=handoff)


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
        return _failure(_CMD_DISCARD, "workflow-state.md not found")
    revision_dir = ws_path.parent.resolve()
    try:
        pointer = load_discussion_pointer(revision_dir)
    except (OSError, ValueError) as exc:
        return _failure(_CMD_DISCARD, str(exc))
    focus = str(pointer["focus"])
    layout = eval_layout_for_revision(revision_dir)
    slice_dir = revision_dir if layout == "legacy-root" else (revision_dir / focus)
    staging = (slice_dir / _STAGING_ROOT / lease_id).resolve()
    if staging.is_dir():
        shutil.rmtree(staging, ignore_errors=True)
    return _success(_CMD_DISCARD, lease_id=lease_id)


def commit_artifacts(
    cycle_id: str,
    project_root: Path,
    *,
    manifest: dict[str, Any],
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Publish staged artifact under current focus if lease is still valid."""
    errors = validate_artifact_manifest(manifest)
    if errors:
        return _failure(_CMD_COMMIT, "; ".join(errors))

    root = project_root.resolve()
    ws_path = workflow_state_path(cycle_id, root, profile_id)
    if not ws_path.is_file():
        return _failure(_CMD_COMMIT, "workflow-state.md not found")
    revision_dir = ws_path.parent.resolve()
    try:
        pointer = load_discussion_pointer(revision_dir)
    except (OSError, ValueError) as exc:
        return _failure(_CMD_COMMIT, str(exc))

    focus = str(pointer["focus"])
    phase = str(pointer["by_id"][focus].get("phase", ""))
    if phase != "evaluating":
        return _failure(
            _CMD_COMMIT,
            f"focus {focus!r} phase is {phase!r}, expected 'evaluating'",
        )
    if focus != str(manifest["focus_l"]):
        return _failure(
            _CMD_COMMIT,
            f"stale handoff: focus is {focus!r}, manifest focus_l is {manifest['focus_l']!r}",
        )
    fingerprint = pointer_fingerprint(pointer)
    if fingerprint != str(manifest["pointer_fingerprint"]):
        return _failure(_CMD_COMMIT, "stale handoff: pointer_fingerprint mismatch")

    layout = eval_layout_for_revision(revision_dir)
    slice_dir = revision_dir if layout == "legacy-root" else (revision_dir / focus)
    staging = (slice_dir / _STAGING_ROOT / str(manifest["lease_id"])).resolve()
    if not staging.is_dir():
        return _failure(_CMD_COMMIT, f"staging dir missing: {staging}")
    try:
        meta = _load_lease_meta(staging)
    except ValueError as exc:
        return _failure(_CMD_COMMIT, str(exc))
    if str(meta.get("pointer_fingerprint")) != fingerprint:
        shutil.rmtree(staging, ignore_errors=True)
        return _failure(_CMD_COMMIT, "stale lease: pointer changed; staging discarded")

    staged = staging / str(manifest["staged_relative_path"])
    if not staged.is_file():
        return _failure(_CMD_COMMIT, f"staged artifact missing: {staged}")
    digest = _file_digest(staged)
    if digest != str(manifest["artifact_digest"]):
        return _failure(_CMD_COMMIT, "artifact digest mismatch")

    evaluate_round = int(manifest["evaluate_round"])
    final_dir = (
        revision_dir / f"evaluate{evaluate_round}"
        if layout == "legacy-root"
        else slice_dir / f"evaluate{evaluate_round}"
    )
    final_path = final_dir / str(manifest["final_relative_path"])
    tmp_publish = final_path.with_name(final_path.name + ".tmp")
    try:
        final_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged, tmp_publish)
        _atomic_replace(tmp_publish, final_path)
    except OSError as exc:
        if tmp_publish.exists():
            tmp_publish.unlink(missing_ok=True)
        return _failure(_CMD_COMMIT, f"publish failed: {exc}")

    state_patch = manifest.get("state_patch") or {}
    if state_patch:
        es_path = (
            revision_dir / "evaluate-state.md"
            if layout == "legacy-root"
            else slice_dir / "evaluate-state.md"
        )
        if not es_path.is_file():
            return _failure(_CMD_COMMIT, f"evaluate-state.md missing: {es_path}")
        # Deferred: Eval control applies state patches via evaluate_state_ops.
        # Commit only guarantees artifact publish under valid lease.

    shutil.rmtree(staging, ignore_errors=True)
    return _success(
        _CMD_COMMIT,
        published_path=final_path.as_posix(),
        focus_l=focus,
        evaluate_round=evaluate_round,
    )


def commit_evaluate_state(
    cycle_id: str,
    project_root: Path,
    *,
    staged_state_path: Path,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    set_phase_evaluating: bool = False,
    previous_done_required: bool = False,
) -> dict[str, Any]:
    """Atomically publish a staged evaluate-state.md under the current focus.

    When ``previous_done_required`` is true (next-round path), the formal state
    must already exist with ``eval_status=done``; failure leaves it untouched.
    When ``set_phase_evaluating`` is true (first enter), focus phase becomes
    ``evaluating`` only after the state file is published.
    """
    root = project_root.resolve()
    staged = Path(staged_state_path).resolve()
    if not staged.is_file():
        return _failure(_CMD_COMMIT_STATE, f"staged state missing: {staged}")

    ws_path = workflow_state_path(cycle_id, root, profile_id)
    if not ws_path.is_file():
        return _failure(_CMD_COMMIT_STATE, "workflow-state.md not found")
    revision_dir = ws_path.parent.resolve()
    try:
        pointer = load_discussion_pointer(revision_dir)
    except (OSError, ValueError) as exc:
        return _failure(_CMD_COMMIT_STATE, str(exc))
    focus = str(pointer["focus"])
    cell = pointer["by_id"][focus]
    phase = str(cell.get("phase", ""))
    if set_phase_evaluating:
        if phase not in {"in_progress", "evaluating"}:
            return _failure(
                _CMD_COMMIT_STATE,
                f"focus {focus!r} phase is {phase!r}, expected in_progress/evaluating",
            )
    elif phase != "evaluating":
        return _failure(
            _CMD_COMMIT_STATE,
            f"focus {focus!r} phase is {phase!r}, expected 'evaluating'",
        )

    layout = eval_layout_for_revision(revision_dir)
    active_doc = load_active_doc_from_cycle(cycle_id, root, profile_id=profile_id)
    es_rel = evaluate_state_path_for_layout(
        cycle_id,
        active_doc,
        profile_id,
        root,
        layout=layout,
        focus_l=focus,
    )
    formal = (root / es_rel).resolve()
    if previous_done_required:
        if not formal.is_file():
            return _failure(_CMD_COMMIT_STATE, "previous evaluate-state.md missing")
        if _read_eval_status(formal) != "done":
            return _failure(
                _CMD_COMMIT_STATE,
                "previous evaluate-state.md is not done; refusing next-round publish",
            )

    backup = formal.with_suffix(formal.suffix + ".bak") if formal.is_file() else None
    try:
        if backup is not None:
            shutil.copy2(formal, backup)
        _atomic_replace(staged, formal)
        if set_phase_evaluating and phase != "evaluating":
            from dependency_tree_schema import load_dependency_tree  # noqa: WPS433
            from discussion_pointer_schema import save_discussion_pointer  # noqa: WPS433

            tree = load_dependency_tree(revision_dir)
            cell["phase"] = "evaluating"
            cell["acceptance"] = "pending"
            save_discussion_pointer(revision_dir, pointer, tree=tree)
    except (OSError, ValueError) as exc:
        if backup is not None and backup.is_file() and not formal.is_file():
            shutil.copy2(backup, formal)
        return _failure(_CMD_COMMIT_STATE, str(exc))
    finally:
        if backup is not None and backup.is_file():
            backup.unlink(missing_ok=True)

    return _success(
        _CMD_COMMIT_STATE,
        evaluate_state_path=formal.as_posix(),
        focus_l=focus,
        layout=layout,
    )


def _active_target_and_staging(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str,
    command: str,
) -> tuple[Path, Path, str] | dict[str, Any]:
    """Resolve the formal document and current valid Eval lease staging."""
    root = project_root.resolve()
    ws_path = workflow_state_path(cycle_id, root, profile_id)
    if not ws_path.is_file():
        return _failure(command, "workflow-state.md not found")
    revision_dir = ws_path.parent.resolve()
    try:
        pointer = load_discussion_pointer(revision_dir)
    except (OSError, ValueError) as exc:
        return _failure(command, str(exc))
    focus = str(pointer["focus"])
    if str(pointer["by_id"][focus].get("phase", "")) != "evaluating":
        return _failure(command, f"focus {focus!r} is not evaluating")
    layout = eval_layout_for_revision(revision_dir)
    slice_dir = revision_dir if layout == "legacy-root" else revision_dir / focus
    staging_root = (slice_dir / _STAGING_ROOT).resolve()
    active_doc = load_active_doc_from_cycle(cycle_id, root, profile_id=profile_id)
    target = (root / document_path(cycle_id, active_doc, profile_id, root)).resolve()
    return target, staging_root, pointer_fingerprint(pointer)


def _current_lease_dir(
    staging_root: Path,
    *,
    lease_id: str,
    fingerprint: str,
    command: str,
) -> Path | dict[str, Any]:
    if not lease_id:
        return _failure(command, "lease_id is required")
    lease_dir = (staging_root / lease_id).resolve()
    try:
        lease_dir.relative_to(staging_root)
    except ValueError:
        return _failure(command, "lease_id resolves outside Eval staging")
    if not lease_dir.is_dir():
        return _failure(command, f"lease staging missing: {lease_dir}")
    try:
        meta = _load_lease_meta(lease_dir)
    except ValueError as exc:
        return _failure(command, str(exc))
    if str(meta.get("pointer_fingerprint")) != fingerprint:
        return _failure(command, "stale lease: pointer changed")
    return lease_dir


def _lease_scoped_path(
    staging_root: Path,
    candidate: Path,
    *,
    command: str,
) -> Path | dict[str, Any]:
    resolved = candidate.resolve()
    try:
        resolved.relative_to(staging_root)
    except ValueError:
        return _failure(command, "staged target is outside Eval lease staging")
    if not resolved.is_file():
        return _failure(command, f"staged target missing: {resolved}")
    return resolved


def commit_remediation_target(
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
        cycle_id, project_root, profile_id=profile_id, command=_CMD_COMMIT_TARGET
    )
    if isinstance(resolved, dict):
        return resolved
    target, staging_root, fingerprint = resolved
    lease_dir = _current_lease_dir(
        staging_root,
        lease_id=lease_id,
        fingerprint=fingerprint,
        command=_CMD_COMMIT_TARGET,
    )
    if isinstance(lease_dir, dict):
        return lease_dir
    staged = _lease_scoped_path(lease_dir, staged_target_path, command=_CMD_COMMIT_TARGET)
    if isinstance(staged, dict):
        return staged
    if not target.is_file():
        return _failure(_CMD_COMMIT_TARGET, f"target document missing: {target}")
    if _file_digest(target) != base_digest:
        return _failure(_CMD_COMMIT_TARGET, "target base digest mismatch")
    try:
        replacement = target.with_name(target.name + ".eval-remediation.tmp")
        shutil.copy2(staged, replacement)
        _atomic_replace(replacement, target)
    except OSError as exc:
        return _failure(_CMD_COMMIT_TARGET, f"target publish failed: {exc}")
    return _success(
        _CMD_COMMIT_TARGET,
        target_path=target.as_posix(),
        target_digest=_file_digest(target),
    )


def restore_remediation_target(
    cycle_id: str,
    project_root: Path,
    *,
    snapshot_path: Path,
    expected_digest: str,
    lease_id: str,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Restore an Eval snapshot when a later Eval-owned publication fails."""
    resolved = _active_target_and_staging(
        cycle_id, project_root, profile_id=profile_id, command=_CMD_RESTORE_TARGET
    )
    if isinstance(resolved, dict):
        return resolved
    target, staging_root, fingerprint = resolved
    lease_dir = _current_lease_dir(
        staging_root,
        lease_id=lease_id,
        fingerprint=fingerprint,
        command=_CMD_RESTORE_TARGET,
    )
    if isinstance(lease_dir, dict):
        return lease_dir
    snapshot = _lease_scoped_path(lease_dir, snapshot_path, command=_CMD_RESTORE_TARGET)
    if isinstance(snapshot, dict):
        return snapshot
    if not target.is_file() or _file_digest(target) != expected_digest:
        return _failure(_CMD_RESTORE_TARGET, "target changed before rollback")
    try:
        replacement = target.with_name(target.name + ".eval-remediation.tmp")
        shutil.copy2(snapshot, replacement)
        _atomic_replace(replacement, target)
    except OSError as exc:
        return _failure(_CMD_RESTORE_TARGET, f"target rollback failed: {exc}")
    return _success(_CMD_RESTORE_TARGET, target_path=target.as_posix())


def resolve_evaluate_state_abs(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    """Shared resolver for abandon/resume/eval: legacy-root or per-L state path.

    If a revision-root ``evaluate-state.md`` still exists (including terminal
    abandoned/done), prefer it so Compose exit commands can finish the legacy
    session. New Evaluating handoffs use ``eval_layout_for_revision`` instead.
    """
    root = project_root.resolve()
    revision_dir = workflow_state_path(cycle_id, root, profile_id).parent.resolve()
    root_es = revision_dir / "evaluate-state.md"
    if root_es.is_file():
        return root_es.resolve()
    active_doc = load_active_doc_from_cycle(cycle_id, root, profile_id=profile_id)
    focus = "L1"
    pointer_path = revision_dir / DISCUSSION_POINTER_FILENAME
    if pointer_path.is_file():
        focus = str(load_discussion_pointer(revision_dir)["focus"])
    rel = evaluate_state_path_for_layout(
        cycle_id,
        active_doc,
        profile_id,
        root,
        layout="per-l",
        focus_l=focus,
    )
    return (root / rel).resolve()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compose EvalHandoff control")
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--profile", default=DEFAULT_COMPOSE_PROFILE_ID)
    sub = parser.add_subparsers(dest="command", required=True)

    req = sub.add_parser(_CMD_REQUEST, help="Build EvalHandoff for current focus L")
    req.add_argument(
        "--allow-non-evaluating",
        action="store_true",
        help="Allow handoff when focus is not evaluating (tests / prepare)",
    )

    commit = sub.add_parser(_CMD_COMMIT, help="Publish staged artifact under valid lease")
    commit.add_argument("--manifest-json", required=True, help="Artifact manifest JSON")

    commit_state = sub.add_parser(
        _CMD_COMMIT_STATE, help="Atomically publish staged evaluate-state.md"
    )
    commit_state.add_argument("--staged-state", type=Path, required=True)
    commit_state.add_argument(
        "--set-phase-evaluating",
        action="store_true",
        help="Set focus phase=evaluating after publishing state (first enter)",
    )
    commit_state.add_argument(
        "--previous-done-required",
        action="store_true",
        help="Require existing formal state to be eval_status=done (next round)",
    )

    discard = sub.add_parser(_CMD_DISCARD, help="Discard lease staging directory")
    discard.add_argument("--lease-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    root = args.project_root.resolve()
    profile_id = str(args.profile).strip()
    cycle_id = str(args.cycle_id).strip()

    if args.command == _CMD_REQUEST:
        return _emit(
            request_handoff(
                cycle_id,
                root,
                profile_id=profile_id,
                require_evaluating=not args.allow_non_evaluating,
            )
        )
    if args.command == _CMD_COMMIT:
        try:
            manifest = json.loads(args.manifest_json)
        except json.JSONDecodeError as exc:
            return _emit(_failure(_CMD_COMMIT, f"invalid manifest JSON: {exc}"))
        return _emit(
            commit_artifacts(
                cycle_id, root, manifest=manifest, profile_id=profile_id
            )
        )
    if args.command == _CMD_COMMIT_STATE:
        return _emit(
            commit_evaluate_state(
                cycle_id,
                root,
                staged_state_path=args.staged_state,
                profile_id=profile_id,
                set_phase_evaluating=bool(args.set_phase_evaluating),
                previous_done_required=bool(args.previous_done_required),
            )
        )
    if args.command == _CMD_DISCARD:
        return _emit(
            discard_staging_for_cycle(
                cycle_id,
                root,
                lease_id=str(args.lease_id),
                profile_id=profile_id,
            )
        )
    return _emit(_failure(str(args.command), f"unknown command: {args.command}"))


if __name__ == "__main__":
    raise SystemExit(main())
