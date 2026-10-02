#!/usr/bin/env python3
"""Handoff and artifact publish for the lulu-tasks Eval adapter."""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[1]
_EVAL_SCRIPTS = Path(__file__).resolve().parents[3] / "eval" / "scripts"
for _path in (_SCRIPTS, _EVAL_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from eval_admission import file_digest
from eval_handoff_schema import (
    build_eval_handoff_v2,
    validate_artifact_manifest_v2,
    validate_eval_handoff_v2,
)
from evaluate_state_schema import load_evaluate_state, save_evaluate_state
from tt_eval_runtime_schema import (
    allocate_lease,
    evaluate_dir,
    evaluate_state_path,
    exit_evaluating_runtime,
    load_runtime,
    runtime_path,
)
from tt_eval_target_schema import eval_target_path

_EVAL_CAPABILITY = "full-remediation"
_COMPLETION_MODE = "return_to_caller"
_SESSION_KEY = "tasks"


def request_eval_handoff(
    adapter: Any,
    cycle_id: str,
    project_root: Path,
    *,
    require_evaluating: bool = True,
) -> dict[str, Any]:
    session_dir = adapter.session_dir(cycle_id, project_root)
    runtime = load_runtime(runtime_path(session_dir))
    if require_evaluating and runtime.get("focus_phase") != "evaluating":
        raise ValueError("tasks EvalHandoff requires focus_phase=evaluating")
    runtime = allocate_lease(session_dir, runtime)
    adapter.save_runtime(cycle_id, project_root, runtime)
    evaluate_round = int(runtime.get("evaluate_round") or 1)
    target = eval_target_path(session_dir).resolve()
    if not target.is_file():
        raise ValueError(f"work-order-eval-target.md missing: {target}")
    handoff = build_eval_handoff_v2(
        workflow_id=adapter.WORKFLOW_ID,
        cycle_id=cycle_id,
        session_key=_SESSION_KEY,
        evaluate_round=evaluate_round,
        evaluate_state_path=evaluate_state_path(session_dir).resolve().as_posix(),
        evaluate_dir=evaluate_dir(session_dir, evaluate_round).resolve().as_posix(),
        write_staging_dir=str(runtime["write_staging_dir"]),
        lease_id=str(runtime["active_lease_id"]),
        bindings={"eval_target_path": target.as_posix()},
        policy_context={
            "mode": "tech",
            "cycle_type": "feature",
            "upstream_baseline_ref": "",
            "eval_capability": _EVAL_CAPABILITY,
            "completion_mode": _COMPLETION_MODE,
        },
    )
    errors = validate_eval_handoff_v2(handoff)
    if errors:
        raise ValueError("; ".join(errors))
    return handoff


def commit_eval_artifacts(
    adapter: Any,
    cycle_id: str,
    project_root: Path,
    *,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    errors = validate_artifact_manifest_v2(manifest)
    if errors:
        return {"ok": False, "error": "; ".join(errors)}
    session_dir = adapter.session_dir(cycle_id, project_root)
    runtime = load_runtime(runtime_path(session_dir))
    if str(manifest.get("lease_id", "")) != str(runtime.get("active_lease_id", "")):
        return {"ok": False, "error": "lease_id mismatch"}
    staging = Path(str(runtime["write_staging_dir"]))
    staged = staging / str(manifest["staged_relative_path"])
    if not staged.is_file():
        return {"ok": False, "error": f"staged artifact missing: {staged}"}
    digest = hashlib.sha256(staged.read_bytes()).hexdigest()
    if digest != str(manifest.get("artifact_digest", "")):
        return {"ok": False, "error": "artifact digest mismatch"}
    final = evaluate_dir(session_dir, int(manifest["evaluate_round"])) / str(
        manifest["final_relative_path"]
    )
    final.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(staged, final)
    state_patch = manifest.get("state_patch") or {}
    if state_patch:
        es_path = evaluate_state_path(session_dir)
        data = load_evaluate_state(es_path)
        data.update({str(key): str(value) for key, value in state_patch.items()})
        save_evaluate_state(es_path, data, merge=True)
    return {"ok": True}


def commit_evaluate_state(
    adapter: Any,
    cycle_id: str,
    project_root: Path,
    *,
    staged_state_path: Path,
    set_phase_evaluating: bool = False,
    previous_done_required: bool = False,
) -> dict[str, Any]:
    del set_phase_evaluating, previous_done_required
    session_dir = adapter.session_dir(cycle_id, project_root)
    if not staged_state_path.is_file():
        return {"ok": False, "error": f"staged state missing: {staged_state_path}"}
    es_path = evaluate_state_path(session_dir)
    es_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(staged_state_path, es_path)
    return {"ok": True}


def discard_eval_staging(
    adapter: Any,
    cycle_id: str,
    project_root: Path,
    *,
    lease_id: str,
) -> dict[str, Any]:
    session_dir = adapter.session_dir(cycle_id, project_root)
    runtime = load_runtime(runtime_path(session_dir))
    staging = str(runtime.get("write_staging_dir") or "")
    if staging and Path(staging).name == lease_id:
        shutil.rmtree(staging, ignore_errors=True)
    runtime["active_lease_id"] = ""
    runtime["write_staging_dir"] = ""
    adapter.save_runtime(cycle_id, project_root, runtime)
    return {"ok": True}


def read_eval_target_digest(target_path: Path) -> str:
    return file_digest(Path(target_path))


def finalize_eval_outcome(
    adapter: Any,
    cycle_id: str,
    project_root: Path,
    *,
    outcome: str,
    issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    session_dir = adapter.session_dir(cycle_id, project_root)
    runtime = exit_evaluating_runtime(
        load_runtime(runtime_path(session_dir)),
        outcome=outcome,
    )
    adapter.save_runtime(cycle_id, project_root, runtime)
    return {
        "ok": True,
        "outcome": outcome,
        "evaluate_round": int(runtime.get("evaluate_round") or 0),
        "issues": issues or [],
    }
