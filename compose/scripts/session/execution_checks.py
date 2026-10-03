#!/usr/bin/env python3
"""Completion checks, stamps and eval-run bookkeeping for the execution dir."""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from deductive_gate import evaluate_deductive_gate  # noqa: E402
from execution_state_schema import execution_fingerprint  # noqa: E402
from facts_schema import facts_path, save_facts, strip_derived_facts, validate_facts  # noqa: E402

FACT_INTAKE_STAMP = "_fact_intake.complete"
INDUCTIVE_STAMP = "_inductive.complete"
DEDUCTIVE_STAMP = "_deductive.complete"
WRITING_STAMP = "_writing.complete"
EVAL_RUN_FILE = "_eval_run.json"
EVAL_STAGING_DIR = ".eval-staging"
INDUCTIVE_GATE_STATE_FILE = "inductive-gate-state.json"
_G5_RESIDUE_FILES = (
    "provenance-gate-state.json",
    "provenance-trace-intent.json",
    "provenance-trace-scope.json",
    "provenance-trace-norm.json",
)


def has_stamp(execution_dir: Path, name: str) -> bool:
    return (Path(execution_dir) / name).is_file()


def write_stamp(execution_dir: Path, name: str) -> None:
    path = Path(execution_dir) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ok\n", encoding="utf-8")


def clear_stamp(execution_dir: Path, name: str) -> None:
    path = Path(execution_dir) / name
    if path.is_file():
        path.unlink()


def eval_run_path(execution_dir: Path) -> Path:
    return Path(execution_dir) / EVAL_RUN_FILE


def load_eval_run(execution_dir: Path) -> dict[str, Any] | None:
    path = eval_run_path(execution_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_eval_run(execution_dir: Path, state: dict[str, Any]) -> str:
    run_id = uuid.uuid4().hex
    payload = {"eval_run_id": run_id, "execution_fingerprint": execution_fingerprint(state)}
    path = eval_run_path(execution_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return run_id


def eval_run_is_current(execution_dir: Path, state: dict[str, Any]) -> str | None:
    """Return an error when no eval run exists or it predates the current state."""
    meta = load_eval_run(execution_dir)
    if meta is None:
        return "missing eval_run_id"
    if str(meta.get("execution_fingerprint", "")) != execution_fingerprint(state):
        return "eval_run_id is stale"
    return None


def clear_eval_run(execution_dir: Path) -> None:
    path = eval_run_path(execution_dir)
    if path.is_file():
        path.unlink()
    staging = Path(execution_dir) / EVAL_STAGING_DIR
    if staging.is_dir():
        shutil.rmtree(staging, ignore_errors=True)


def _ensure_inductive_imports() -> None:
    inductive = _SCRIPTS / "inductive"
    for path in (inductive, *kernel_bootstrap.inductive_schema_dirs()):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def purge_g5_residue(*directories: Path) -> None:
    seen: set[Path] = set()
    for directory in directories:
        resolved = Path(directory).resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        for name in _G5_RESIDUE_FILES:
            path = resolved / name
            if path.is_file():
                path.unlink()


def init_inductive_bundle(execution_dir: Path, cycle_id: str, profile_id: str) -> None:
    from compose_state_lock import compose_state_lock  # noqa: WPS433

    _ensure_inductive_imports()
    from inductive_gate_state_schema import init_gate_state, save_gate_state  # noqa: WPS433
    from open_point_store import ensure_idle_bundle  # noqa: WPS433

    gate_path = Path(execution_dir) / INDUCTIVE_GATE_STATE_FILE
    with compose_state_lock(execution_dir):
        ensure_idle_bundle(execution_dir)
        purge_g5_residue(execution_dir)
        if gate_path.is_file():
            try:
                raw = json.loads(gate_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw = {}
            if isinstance(raw, dict) and str(raw.get("active_gate", "")).strip() == "G5":
                gate_path.unlink()
        if not gate_path.is_file():
            save_gate_state(gate_path, init_gate_state(cycle_id=cycle_id, stage=profile_id))


def _open_point_txn_block(execution_dir: Path) -> str | None:
    txn_path = Path(execution_dir) / "_open-point-txn.json"
    if not txn_path.is_file():
        return None
    from compose_state_lock import compose_state_lock  # noqa: WPS433

    _ensure_inductive_imports()
    from open_point_store import RepairRequiredError, reconcile  # noqa: WPS433

    try:
        with compose_state_lock(execution_dir):
            reconcile(execution_dir)
            if txn_path.is_file():
                return "pending open-point transaction"
    except RepairRequiredError:
        return "open-point transaction repair_required"
    return None


def inductive_gate_closed(execution_dir: Path) -> bool:
    gate = Path(execution_dir) / INDUCTIVE_GATE_STATE_FILE
    if not gate.is_file():
        return False
    try:
        data = json.loads(gate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    active = str(data.get("active_gate", "")).strip()
    if active in {"G4", "G5"}:
        return False
    g3_ok = str(data.get("gates", {}).get("G3", {}).get("status", "")).lower() == "closed"
    return g3_ok and active == "complete"


def deductive_gate_closed(revision_dir: Path) -> bool:
    return evaluate_deductive_gate(revision_dir) is None


def fact_intake_complete_error(execution_dir: Path, *, inductive: bool) -> str | None:
    path = facts_path(execution_dir)
    if not path.is_file():
        return "fact-intake complete check failed: facts missing"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return f"fact-intake complete check failed: {exc}"
    errors = validate_facts(data, require_seed_origin=inductive)
    if errors:
        return "fact-intake complete check failed: " + "; ".join(errors)
    return None


def inductive_complete_error(execution_dir: Path) -> str | None:
    if not facts_path(execution_dir).is_file():
        return "inductive complete check failed: facts missing"
    if has_stamp(execution_dir, INDUCTIVE_STAMP):
        return None
    txn_err = _open_point_txn_block(execution_dir)
    if txn_err:
        return f"inductive complete check failed: {txn_err}"
    if not inductive_gate_closed(execution_dir):
        return "inductive complete check failed"
    return None


def deductive_complete_error(revision_dir: Path, execution_dir: Path) -> str | None:
    if not facts_path(execution_dir).is_file():
        return "deductive complete check failed: facts missing"
    if has_stamp(execution_dir, DEDUCTIVE_STAMP):
        return None
    if not deductive_gate_closed(revision_dir):
        return "deductive complete check failed"
    return None


def strip_derived(execution_dir: Path) -> None:
    path = facts_path(execution_dir)
    if not path.is_file():
        return
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(raw, list) or not raw:
        return
    kept = strip_derived_facts(raw)
    if len(kept) != len(raw):
        save_facts(path, kept)


def reset_stage_complete(
    execution_dir: Path,
    *,
    cycle_id: str,
    profile_id: str,
    init_inductive: bool,
) -> None:
    for name in (INDUCTIVE_STAMP, DEDUCTIVE_STAMP, WRITING_STAMP):
        clear_stamp(execution_dir, name)
    gate = Path(execution_dir) / INDUCTIVE_GATE_STATE_FILE
    if gate.is_file():
        gate.unlink()
    purge_g5_residue(execution_dir)
    if init_inductive:
        init_inductive_bundle(execution_dir, cycle_id, profile_id)
