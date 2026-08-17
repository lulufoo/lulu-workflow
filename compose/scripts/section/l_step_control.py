#!/usr/bin/env python3
"""Single-L step control for compose (`$L_STEP`).

Subcommands:
    status
    enter-fact-intake / complete-fact-intake
    enter-inductive / complete-inductive
    enter-deductive / complete-deductive
    enter-writing / complete-writing
    enter-freeedit
    reverse-to-inductive / reverse-to-deductive / reverse-to-writing
    enter-evaluating
    accept --confirm / fix --confirm / re-evaluate --confirm / reopen --confirm

Writes ``by_id[focus].state`` only. Does not change order, focus, or frozen.

Design rationale:
docs/domain/archive/compose/archive-33.0/compose-l-execution-subdesign.md
docs/domain/archive/compose/archive-35.0/compose-fact-intake-extract-subdesign.md
docs/domain/archive/compose/archive-35.0/compose-producer-serial-subdesign.md
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_session import document_file_path, load_active_doc_for_profile  # noqa: E402
from delivered_refs_schema import serialize_delivered_refs  # noqa: E402
from facts_schema import (  # noqa: E402
    facts_path,
    save_facts,
    strip_derived_facts,
    validate_facts,
)
from deductive_gate import evaluate_deductive_gate  # noqa: E402
from l_ledger_schema import (  # noqa: E402
    active_slice_dir,
    l_ledger_path,
    ledger_fingerprint,
    load_l_ledger,
    save_l_ledger,
)
from l_transition_kernel import (  # noqa: E402
    IllegalTransition,
    step_abort_evaluating,
    step_accept,
    step_enter_deductive,
    step_enter_evaluating,
    step_enter_fact_intake,
    step_enter_freeedit,
    step_enter_inductive,
    step_enter_writing,
    step_fix,
    step_reopen,
    step_reverse_to_deductive,
    step_reverse_to_inductive,
    step_reverse_to_writing,
)
from revision_lock import LockTimeout, revision_lock, session_lock  # noqa: E402
from resolved_refs_schema import (  # noqa: E402
    intent_baseline_from_workflow,
    norm_constraint_from_workflow,
    primary_scope_from_workflow,
)
from workflow_common import detect_cycle_type  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, load_profile, resolve_profile_id  # noqa: E402
from workflow_profile_paths import (  # noqa: E402
    doc_dir,
    inductive_out_dir,
    session_state_path,
)
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
)
from writing_compose_validation import validate_writing_artifacts  # noqa: E402

_CMD_STATUS = "status"
_CMD_ENTER_FACT_INTAKE = "enter-fact-intake"
_CMD_COMPLETE_FACT_INTAKE = "complete-fact-intake"
_CMD_ENTER_INDUCTIVE = "enter-inductive"
_CMD_COMPLETE_INDUCTIVE = "complete-inductive"
_CMD_ENTER_DEDUCTIVE = "enter-deductive"
_CMD_COMPLETE_DEDUCTIVE = "complete-deductive"
_CMD_ENTER_WRITING = "enter-writing"
_CMD_COMPLETE_WRITING = "complete-writing"
_CMD_ENTER_FREEEDIT = "enter-freeedit"
_CMD_REVERSE_INDUCTIVE = "reverse-to-inductive"
_CMD_REVERSE_DEDUCTIVE = "reverse-to-deductive"
_CMD_REVERSE_WRITING = "reverse-to-writing"
_CMD_ENTER_EVALUATING = "enter-evaluating"
_CMD_ACCEPT = "accept"
_CMD_FIX = "fix"
_CMD_RE_EVALUATE = "re-evaluate"
_CMD_REOPEN = "reopen"
_CONFIRM_CMDS = frozenset({_CMD_ACCEPT, _CMD_FIX, _CMD_RE_EVALUATE, _CMD_REOPEN})
_MUTATIONS = frozenset(
    {
        _CMD_ENTER_FACT_INTAKE,
        _CMD_ENTER_INDUCTIVE,
        _CMD_ENTER_DEDUCTIVE,
        _CMD_ENTER_WRITING,
        _CMD_ENTER_FREEEDIT,
        _CMD_REVERSE_INDUCTIVE,
        _CMD_REVERSE_DEDUCTIVE,
        _CMD_REVERSE_WRITING,
        _CMD_ENTER_EVALUATING,
        _CMD_ACCEPT,
        _CMD_FIX,
        _CMD_RE_EVALUATE,
        _CMD_REOPEN,
    }
)
_FACT_INTAKE_STAMP = "_fact_intake.complete"
_INDUCTIVE_STAMP = "_inductive.complete"
_DEDUCTIVE_STAMP = "_deductive.complete"
_WRITING_STAMP = "_writing.complete"
_EVAL_RUN_FILE = "_eval_run.json"
_INDUCTIVE_GATE_STATE_FILE = "inductive-gate-state.json"
_G5_RESIDUE_FILES = (
    "provenance-gate-state.json",
    "provenance-trace-intent.json",
    "provenance-trace-scope.json",
    "provenance-trace-norm.json",
)


def _success(command: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "command": command}
    payload.update(extra)
    return payload


def _failure(command: str, code: str, error: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "command": command,
        "code": code,
        "error": error,
    }
    payload.update(extra)
    return payload


def _pipeline_config(cycle_id: str, project_root: Path, profile_id: str) -> dict:
    profile = load_profile(profile_id, project_root=project_root, cycle_id=cycle_id)
    return profile.get("pipeline") or {}


def _revision_dir(cycle_id: str, project_root: Path, profile_id: str) -> Path:
    active_doc = load_active_doc_for_profile(cycle_id, project_root, profile_id)
    return (
        project_root / doc_dir(cycle_id, active_doc, profile_id, project_root)
    ).resolve()


def _session_state(cycle_id: str, project_root: Path, profile_id: str) -> str:
    ws_path = resolve_workflow_state_path_from_cycle(
        cycle_id, project_root, profile_id=profile_id
    )
    if not ws_path.is_file():
        raise FileNotFoundError("workflow-state.md not found (run start; then leave-split)")
    return str(load_workflow_state(ws_path)["current_state"]).strip()


def _require_working(
    command: str,
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> dict[str, Any] | None:
    try:
        current = _session_state(cycle_id, project_root, profile_id)
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _failure(command, "wrong_session_state", str(exc))
    if current == "Split":
        return _failure(
            command,
            "wrong_session_state",
            "session is still Split; run leave-split",
            session_state=current,
        )
    if current != "Working":
        return _failure(
            command,
            "wrong_session_state",
            f"session current_state is {current!r} (expected Working)",
            session_state=current,
        )
    return None


def _stamp_path(slice_dir: Path, name: str) -> Path:
    return Path(slice_dir) / name


def _has_stamp(slice_dir: Path, name: str) -> bool:
    return _stamp_path(slice_dir, name).is_file()


def _write_stamp(slice_dir: Path, name: str) -> None:
    path = _stamp_path(slice_dir, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("ok\n", encoding="utf-8")


def _clear_stamp(slice_dir: Path, name: str) -> None:
    path = _stamp_path(slice_dir, name)
    if path.is_file():
        path.unlink()


def _eval_run_path(slice_dir: Path) -> Path:
    return Path(slice_dir) / _EVAL_RUN_FILE


def _load_eval_run(slice_dir: Path) -> dict[str, Any] | None:
    path = _eval_run_path(slice_dir)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


def _write_eval_run(slice_dir: Path, ledger: dict[str, Any]) -> str:
    run_id = uuid.uuid4().hex
    payload = {
        "eval_run_id": run_id,
        "ledger_fingerprint": ledger_fingerprint(ledger),
    }
    path = _eval_run_path(slice_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return run_id


def _inductive_out(cycle_id: str, project_root: Path, profile_id: str) -> Path:
    return (project_root / inductive_out_dir(cycle_id, profile_id, project_root)).resolve()


def _ensure_inductive_imports() -> None:
    inductive = _SCRIPTS / "inductive"
    schema = inductive / "schema"
    for path in (inductive, schema):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def _purge_g5_residue(*directories: Path) -> None:
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


def _init_inductive_slice(slice_dir: Path, cycle_id: str, profile_id: str) -> None:
    from compose_state_lock import compose_state_lock  # noqa: WPS433

    _ensure_inductive_imports()
    from inductive_gate_state_schema import init_gate_state, save_gate_state  # noqa: WPS433
    from open_point_store import ensure_idle_bundle  # noqa: WPS433

    gate_path = Path(slice_dir) / _INDUCTIVE_GATE_STATE_FILE
    with compose_state_lock(slice_dir):
        ensure_idle_bundle(slice_dir)
        _purge_g5_residue(slice_dir)
        if gate_path.is_file():
            try:
                raw = json.loads(gate_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raw = {}
            if isinstance(raw, dict) and str(raw.get("active_gate", "")).strip() == "G5":
                gate_path.unlink()
        if not gate_path.is_file():
            save_gate_state(
                gate_path,
                init_gate_state(cycle_id=cycle_id, stage=profile_id),
            )


def _open_point_txn_block(slice_dir: Path) -> str | None:
    txn_path = Path(slice_dir) / "_open-point-txn.json"
    if not txn_path.is_file():
        return None
    from compose_state_lock import compose_state_lock  # noqa: WPS433

    _ensure_inductive_imports()
    from open_point_store import RepairRequired, reconcile  # noqa: WPS433

    try:
        with compose_state_lock(slice_dir):
            reconcile(slice_dir)
            if txn_path.is_file():
                return "pending open-point transaction"
    except RepairRequired:
        return "open-point transaction repair_required"
    return None


def _opaque_inductive_closed(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> bool:
    out = _inductive_out(cycle_id, project_root, profile_id)
    g4 = out / _INDUCTIVE_GATE_STATE_FILE
    if not g4.is_file():
        return False
    try:
        g4_data = json.loads(g4.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if str(g4_data.get("active_gate", "")).strip() == "G5":
        return False
    g4_ok = str(g4_data.get("gates", {}).get("G4", {}).get("status", "")).lower() == "closed"
    complete_ok = str(g4_data.get("active_gate", "")).strip() == "complete"
    return g4_ok and complete_ok


def _opaque_deductive_closed(revision_dir: Path) -> bool:
    return evaluate_deductive_gate(revision_dir) is None


def _inductive_complete_error(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
    slice_dir: Path,
) -> str | None:
    if not facts_path(slice_dir).is_file():
        return "inductive complete check failed: facts missing"
    if _has_stamp(slice_dir, _INDUCTIVE_STAMP):
        return None
    txn_err = _open_point_txn_block(slice_dir)
    if txn_err:
        return f"inductive complete check failed: {txn_err}"
    if not _opaque_inductive_closed(cycle_id, project_root, profile_id):
        return "inductive complete check failed"
    return None


def _deductive_complete_error(revision_dir: Path, slice_dir: Path) -> str | None:
    if not facts_path(slice_dir).is_file():
        return "deductive complete check failed: facts missing"
    if _has_stamp(slice_dir, _DEDUCTIVE_STAMP):
        return None
    if not _opaque_deductive_closed(revision_dir):
        return "deductive complete check failed"
    return None


def _strip_derived(slice_dir: Path) -> None:
    path = facts_path(slice_dir)
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


def _reset_stage_complete(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
    slice_dir: Path,
    *,
    init_inductive: bool = False,
) -> None:
    _clear_stamp(slice_dir, _INDUCTIVE_STAMP)
    _clear_stamp(slice_dir, _DEDUCTIVE_STAMP)
    _clear_stamp(slice_dir, _WRITING_STAMP)
    out = _inductive_out(cycle_id, project_root, profile_id)
    gate = out / _INDUCTIVE_GATE_STATE_FILE
    if gate.is_file():
        gate.unlink()
    _purge_g5_residue(out, slice_dir)
    if init_inductive:
        _init_inductive_slice(slice_dir, cycle_id, profile_id)


def _scope_doc(revision_dir: Path, cycle_id: str, project_root: Path, profile_id: str) -> Path:
    packaged = revision_dir / "scope-package.json"
    if packaged.is_file():
        return packaged
    from resolved_refs_schema import resolved_scope_ref  # noqa: WPS433

    ref = resolved_scope_ref(revision_dir)
    if ref is not None and str(ref.path).strip():
        path = Path(ref.path)
        if path.is_file():
            return path
    init_ref = primary_scope_from_workflow(cycle_id, project_root, profile_id)
    if init_ref is None:
        raise ValueError("no scope ref available")
    scope_path = Path(init_ref.path).resolve()
    if not scope_path.is_file():
        raise ValueError(f"scope doc not found: {scope_path}")
    return scope_path


def _focus_source_path(revision_dir: Path, scope_path: Path) -> Path:
    from scope_package_convert import (  # noqa: WPS433
        ScopePackageAntiseepError,
        focus_seed_source_path,
        revision_uses_scope_package,
    )
    from scope_package_schema import is_scope_package_path  # noqa: WPS433

    if revision_uses_scope_package(revision_dir) or is_scope_package_path(scope_path):
        try:
            return Path(focus_seed_source_path(revision_dir))
        except ScopePackageAntiseepError:
            raise
    return scope_path


def _format_producer_dispatch(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
    *,
    inductive: bool,
    revision_dir: Path,
) -> str:
    scope_path = _scope_doc(revision_dir, cycle_id, project_root, profile_id)
    intent_refs = intent_baseline_from_workflow(cycle_id, project_root, profile_id)
    norm_refs = norm_constraint_from_workflow(cycle_id, project_root, profile_id)
    source = _focus_source_path(revision_dir, scope_path).as_posix()
    if inductive:
        lines = [
            f"CYCLE_ID:             {cycle_id}",
            f"SCOPE_REF:            {source}",
            f"SOURCE_PATH:          {source}",
            f"INTENT_BASELINE_REFS: {serialize_delivered_refs(intent_refs)}",
            f"NORM_CONSTRAINT_REFS: {serialize_delivered_refs(norm_refs)}",
            f"INDUCTIVE_OUT_DIR:    {_inductive_out(cycle_id, project_root, profile_id).as_posix()}",
        ]
        return "\n".join(lines)
    pipeline = _pipeline_config(cycle_id, project_root, profile_id)
    lines = [
        f"CYCLE_ID:             {cycle_id}",
        f"SCOPE_REF:            {scope_path.as_posix()}",
        f"INTENT_BASELINE_REFS: {serialize_delivered_refs(intent_refs)}",
        f"NORM_CONSTRAINT_REFS: {serialize_delivered_refs(norm_refs)}",
        f"DEDUCTIVE_OUT_DIR:    {revision_dir.as_posix()}",
        f"CODE_GROUNDING:       {str(bool(pipeline.get('code_grounding'))).lower()}",
        f"SOURCE_PATH:          {source}",
    ]
    return "\n".join(lines)


def _format_fact_intake_dispatch(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
    *,
    inductive: bool,
    revision_dir: Path,
) -> str:
    scope_path = _scope_doc(revision_dir, cycle_id, project_root, profile_id)
    source = _focus_source_path(revision_dir, scope_path).as_posix()
    revision = (
        _inductive_out(cycle_id, project_root, profile_id).as_posix()
        if inductive
        else revision_dir.as_posix()
    )
    return "\n".join(
        [
            f"REVISION_DIR:         {revision}",
            f"PROJECT_ROOT:         {project_root.as_posix()}",
            f"CYCLE_ID:             {cycle_id}",
            f"SOURCE_PATH:          {source}",
            f"REQUIRE_SEED_ORIGIN:  {str(inductive).lower()}",
        ]
    )


def _fact_intake_complete_error(slice_dir: Path, *, inductive: bool) -> str | None:
    path = facts_path(slice_dir)
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


def _format_writing_dispatch(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
    revision_dir: Path,
) -> str:
    output_doc = document_file_path(cycle_id, project_root, profile_id)
    code_grounding = bool(
        _pipeline_config(cycle_id, project_root, profile_id).get("code_grounding")
    )
    return "\n".join(
        [
            f"REVISION_DIR:         {revision_dir.as_posix()}",
            f"SCOPE_REF_PATH:       {_scope_doc(revision_dir, cycle_id, project_root, profile_id).as_posix()}",
            f"OUTPUT_DOC_PATH:      {output_doc.resolve().as_posix()}",
            f"CYCLE_TYPE:           {detect_cycle_type(cycle_id)}",
            f"CYCLE_ID:             {cycle_id}",
            f"CODE_GROUNDING:       {str(code_grounding).lower()}",
        ]
    )


def derive_step_next_actions(
    state: str,
    *,
    writing_ok: bool,
    freeedit: bool,
    fact_intake_ok: bool = False,
    inductive: bool = False,
    inductive_ok: bool = False,
    deductive_ok: bool = False,
    producer_ok: bool = False,
) -> list[str]:
    del producer_ok
    if state == "Pending":
        return ["enter-fact-intake"]
    if state == "FactIntake":
        if not fact_intake_ok:
            return ["run-fact-intake"]
        return ["enter-inductive"] if inductive else ["enter-deductive"]
    if state == "Inductive":
        return ["enter-deductive"] if inductive_ok else ["run-inductive"]
    if state == "Deductive":
        return ["enter-writing"] if deductive_ok else ["run-deductive"]
    if state == "Writing":
        if not writing_ok:
            return ["run-writing"]
        if freeedit:
            return ["enter-freeedit", "begin-eval-round"]
        return ["begin-eval-round"]
    if state == "FreeEdit":
        actions = ["begin-eval-round"]
        if inductive:
            actions.append("reverse-to-inductive")
        actions.extend(["reverse-to-deductive", "reverse-to-writing"])
        return actions
    if state == "Evaluating":
        return ["accept", "fix", "re-evaluate"]
    if state == "Completed":
        return []
    return []


def _status_payload(
    command: str,
    ledger: dict[str, Any],
    *,
    cycle_id: str,
    project_root: Path,
    profile_id: str,
    revision_dir: Path,
) -> dict[str, Any]:
    focus = str(ledger["focus"])
    cell = ledger["by_id"][focus]
    slice_dir = (revision_dir / focus).resolve()
    pipeline = _pipeline_config(cycle_id, project_root, profile_id)
    inductive = pipeline.get("inductive") is True
    inductive_ok = _inductive_complete_error(
        cycle_id, project_root, profile_id, slice_dir
    ) is None
    if inductive_ok and not _has_stamp(slice_dir, _INDUCTIVE_STAMP):
        inductive_ok = _opaque_inductive_closed(cycle_id, project_root, profile_id)
    deductive_ok = _deductive_complete_error(revision_dir, slice_dir) is None
    if deductive_ok and not _has_stamp(slice_dir, _DEDUCTIVE_STAMP):
        deductive_ok = _opaque_deductive_closed(revision_dir)
    writing_ok = _has_stamp(slice_dir, _WRITING_STAMP)
    fact_intake_ok = _has_stamp(slice_dir, _FACT_INTAKE_STAMP)
    eval_run = _load_eval_run(slice_dir)
    actions = derive_step_next_actions(
        str(cell["state"]),
        writing_ok=writing_ok,
        freeedit=pipeline.get("freeedit") is True,
        fact_intake_ok=fact_intake_ok,
        inductive=inductive,
        inductive_ok=inductive_ok,
        deductive_ok=deductive_ok,
    )
    payload = _success(
        command,
        state=cell["state"],
        inductive_complete=bool(inductive_ok),
        deductive_complete=bool(deductive_ok),
        writing_complete=writing_ok,
        next_actions=actions,
    )
    if eval_run and eval_run.get("eval_run_id"):
        payload["eval_run_id"] = eval_run["eval_run_id"]
    return payload


def _with_revision_lock(
    command: str,
    revision_dir: Path,
    apply: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
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
            return _success(
                command,
                state=new_ledger["by_id"][new_ledger["focus"]]["state"],
                focus=new_ledger["focus"],
            )
    except LockTimeout:
        return _failure(command, "lock_timeout", "revision lock timeout")
    except IllegalTransition as exc:
        return _failure(command, exc.code, str(exc), **exc.extra)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _failure(command, "invalid_ledger", str(exc))


def draft_status(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    path = l_ledger_path(revision_dir)
    if not path.is_file():
        return _failure(
            _CMD_STATUS,
            "unsupported_revision",
            "missing l-ledger.json; open a new revision",
        )
    try:
        with revision_lock(revision_dir, exclusive=False):
            ledger = load_l_ledger(revision_dir)
            return _status_payload(
                _CMD_STATUS,
                ledger,
                cycle_id=cycle_id,
                project_root=project_root,
                profile_id=profile_id,
                revision_dir=revision_dir,
            )
    except LockTimeout:
        return _failure(_CMD_STATUS, "lock_timeout", "revision lock timeout")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return _failure(_CMD_STATUS, "invalid_ledger", str(exc))


def enter_fact_intake(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(
        _CMD_ENTER_FACT_INTAKE, cycle_id, project_root, profile_id
    )
    if blocked:
        return blocked
    pipeline = _pipeline_config(cycle_id, project_root, profile_id)
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    inductive = pipeline.get("inductive") is True
    try:
        dispatch_input = _format_fact_intake_dispatch(
            cycle_id,
            project_root,
            profile_id,
            inductive=inductive,
            revision_dir=revision_dir,
        )
    except (OSError, ValueError) as exc:
        return _failure(_CMD_ENTER_FACT_INTAKE, "illegal_transition", str(exc))

    payload = _with_revision_lock(
        _CMD_ENTER_FACT_INTAKE, revision_dir, step_enter_fact_intake
    )
    if payload.get("ok"):
        payload["dispatch_input"] = dispatch_input
    return payload


def complete_fact_intake(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(
        _CMD_COMPLETE_FACT_INTAKE, cycle_id, project_root, profile_id
    )
    if blocked:
        return blocked
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    try:
        ledger = load_l_ledger(revision_dir)
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _failure(_CMD_COMPLETE_FACT_INTAKE, "unsupported_revision", str(exc))
    focus = str(ledger["focus"])
    state = ledger["by_id"][focus]["state"]
    if state != "FactIntake":
        return _failure(
            _CMD_COMPLETE_FACT_INTAKE,
            "illegal_transition",
            "complete-fact-intake requires FactIntake focus",
            state=state,
        )
    pipeline = _pipeline_config(cycle_id, project_root, profile_id)
    inductive = pipeline.get("inductive") is True
    slice_dir = (revision_dir / focus).resolve()
    err = _fact_intake_complete_error(slice_dir, inductive=inductive)
    if err:
        return _failure(_CMD_COMPLETE_FACT_INTAKE, "fact_intake_incomplete", err)
    _write_stamp(slice_dir, _FACT_INTAKE_STAMP)
    return _success(
        _CMD_COMPLETE_FACT_INTAKE, state=state, fact_intake_complete=True
    )


def enter_inductive(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(_CMD_ENTER_INDUCTIVE, cycle_id, project_root, profile_id)
    if blocked:
        return blocked
    pipeline = _pipeline_config(cycle_id, project_root, profile_id)
    if pipeline.get("inductive") is not True:
        return _failure(
            _CMD_ENTER_INDUCTIVE,
            "illegal_transition",
            "enter-inductive requires pipeline.inductive",
        )
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    try:
        dispatch_input = _format_producer_dispatch(
            cycle_id,
            project_root,
            profile_id,
            inductive=True,
            revision_dir=revision_dir,
        )
    except (OSError, ValueError) as exc:
        return _failure(_CMD_ENTER_INDUCTIVE, "illegal_transition", str(exc))

    def apply(ledger: dict[str, Any]) -> dict[str, Any]:
        focus = str(ledger["focus"])
        slice_dir = (revision_dir / focus).resolve()
        if not _has_stamp(slice_dir, _FACT_INTAKE_STAMP):
            raise IllegalTransition(
                "illegal_transition",
                "enter-inductive requires completed fact intake",
            )
        new = step_enter_inductive(ledger)
        _strip_derived(slice_dir)
        return new

    payload = _with_revision_lock(_CMD_ENTER_INDUCTIVE, revision_dir, apply)
    if payload.get("ok"):
        payload["dispatch_input"] = dispatch_input
        focus = str(payload.get("focus") or "")
        slice_dir = (revision_dir / focus).resolve()
        try:
            _init_inductive_slice(slice_dir, cycle_id, profile_id)
        except (OSError, ValueError) as exc:
            return _failure(_CMD_ENTER_INDUCTIVE, "illegal_transition", str(exc))
    return payload


def complete_inductive(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(
        _CMD_COMPLETE_INDUCTIVE, cycle_id, project_root, profile_id
    )
    if blocked:
        return blocked
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    try:
        ledger = load_l_ledger(revision_dir)
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _failure(_CMD_COMPLETE_INDUCTIVE, "unsupported_revision", str(exc))
    focus = str(ledger["focus"])
    state = ledger["by_id"][focus]["state"]
    if state != "Inductive":
        return _failure(
            _CMD_COMPLETE_INDUCTIVE,
            "illegal_transition",
            "complete-inductive requires Inductive focus",
            state=state,
        )
    slice_dir = (revision_dir / focus).resolve()
    err = _inductive_complete_error(cycle_id, project_root, profile_id, slice_dir)
    if err:
        return _failure(_CMD_COMPLETE_INDUCTIVE, "inductive_incomplete", err)
    _write_stamp(slice_dir, _INDUCTIVE_STAMP)
    return _success(_CMD_COMPLETE_INDUCTIVE, state=state, inductive_complete=True)


def enter_deductive(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(_CMD_ENTER_DEDUCTIVE, cycle_id, project_root, profile_id)
    if blocked:
        return blocked
    pipeline = _pipeline_config(cycle_id, project_root, profile_id)
    inductive = pipeline.get("inductive") is True
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    try:
        dispatch_input = _format_producer_dispatch(
            cycle_id,
            project_root,
            profile_id,
            inductive=False,
            revision_dir=revision_dir,
        )
    except (OSError, ValueError) as exc:
        return _failure(_CMD_ENTER_DEDUCTIVE, "illegal_transition", str(exc))

    def apply(ledger: dict[str, Any]) -> dict[str, Any]:
        focus = str(ledger["focus"])
        state = ledger["by_id"][focus]["state"]
        slice_dir = (revision_dir / focus).resolve()
        if not _has_stamp(slice_dir, _FACT_INTAKE_STAMP):
            raise IllegalTransition(
                "illegal_transition",
                "enter-deductive requires completed fact intake",
            )
        if state == "FactIntake" and inductive:
            raise IllegalTransition(
                "illegal_transition",
                "enter-deductive from FactIntake requires pipeline.inductive=false",
            )
        if state == "Inductive":
            if not inductive:
                raise IllegalTransition(
                    "illegal_transition",
                    "enter-deductive from Inductive requires pipeline.inductive",
                )
            if _inductive_complete_error(
                cycle_id, project_root, profile_id, slice_dir
            ) is not None:
                raise IllegalTransition(
                    "illegal_transition",
                    "enter-deductive requires completed inductive",
                )
        new = step_enter_deductive(ledger)
        _strip_derived(slice_dir)
        return new

    payload = _with_revision_lock(_CMD_ENTER_DEDUCTIVE, revision_dir, apply)
    if payload.get("ok"):
        payload["dispatch_input"] = dispatch_input
    return payload


def complete_deductive(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(
        _CMD_COMPLETE_DEDUCTIVE, cycle_id, project_root, profile_id
    )
    if blocked:
        return blocked
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    try:
        ledger = load_l_ledger(revision_dir)
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _failure(_CMD_COMPLETE_DEDUCTIVE, "unsupported_revision", str(exc))
    focus = str(ledger["focus"])
    state = ledger["by_id"][focus]["state"]
    if state != "Deductive":
        return _failure(
            _CMD_COMPLETE_DEDUCTIVE,
            "illegal_transition",
            "complete-deductive requires Deductive focus",
            state=state,
        )
    slice_dir = (revision_dir / focus).resolve()
    err = _deductive_complete_error(revision_dir, slice_dir)
    if err:
        return _failure(_CMD_COMPLETE_DEDUCTIVE, "deductive_incomplete", err)
    _write_stamp(slice_dir, _DEDUCTIVE_STAMP)
    return _success(_CMD_COMPLETE_DEDUCTIVE, state=state, deductive_complete=True)


def enter_writing(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(_CMD_ENTER_WRITING, cycle_id, project_root, profile_id)
    if blocked:
        return blocked
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    try:
        ledger = load_l_ledger(revision_dir)
        slice_dir = (revision_dir / str(ledger["focus"])).resolve()
        err = _deductive_complete_error(revision_dir, slice_dir)
        if err:
            return _failure(_CMD_ENTER_WRITING, "deductive_incomplete", err)
        if not _has_stamp(slice_dir, _DEDUCTIVE_STAMP):
            if not _opaque_deductive_closed(revision_dir):
                return _failure(
                    _CMD_ENTER_WRITING,
                    "deductive_incomplete",
                    "deductive complete check failed",
                )
            _write_stamp(slice_dir, _DEDUCTIVE_STAMP)
        dispatch_input = _format_writing_dispatch(
            cycle_id, project_root, profile_id, revision_dir
        )
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _failure(_CMD_ENTER_WRITING, "illegal_transition", str(exc))

    payload = _with_revision_lock(
        _CMD_ENTER_WRITING,
        revision_dir,
        step_enter_writing,
    )
    if payload.get("ok"):
        payload["dispatch_input"] = dispatch_input
    return payload


def complete_writing(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(_CMD_COMPLETE_WRITING, cycle_id, project_root, profile_id)
    if blocked:
        return blocked
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    try:
        ledger = load_l_ledger(revision_dir)
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _failure(_CMD_COMPLETE_WRITING, "unsupported_revision", str(exc))
    state = ledger["by_id"][str(ledger["focus"])]["state"]
    if state != "Writing":
        return _failure(
            _CMD_COMPLETE_WRITING,
            "illegal_transition",
            "complete-writing requires Writing focus",
            state=state,
        )
    seed_error = validate_writing_artifacts(
        revision_dir,
        document_file_path(cycle_id, project_root, profile_id),
        project_root,
        profile_id,
    )
    if seed_error:
        return _failure(_CMD_COMPLETE_WRITING, "writing_incomplete", seed_error)
    slice_dir = (revision_dir / str(ledger["focus"])).resolve()
    _write_stamp(slice_dir, _WRITING_STAMP)
    return _success(_CMD_COMPLETE_WRITING, state=state, writing_complete=True)


def enter_freeedit(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(_CMD_ENTER_FREEEDIT, cycle_id, project_root, profile_id)
    if blocked:
        return blocked
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    pipeline = _pipeline_config(cycle_id, project_root, profile_id)
    try:
        ledger = load_l_ledger(revision_dir)
        slice_dir = (revision_dir / str(ledger["focus"])).resolve()
        if not _has_stamp(slice_dir, _WRITING_STAMP):
            return _failure(
                _CMD_ENTER_FREEEDIT,
                "writing_incomplete",
                "writing complete check failed",
            )
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _failure(_CMD_ENTER_FREEEDIT, "illegal_transition", str(exc))
    return _with_revision_lock(
        _CMD_ENTER_FREEEDIT,
        revision_dir,
        lambda ledger: step_enter_freeedit(ledger, {"freeedit": pipeline.get("freeedit") is True}),
    )


def reverse_to_inductive(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(
        _CMD_REVERSE_INDUCTIVE, cycle_id, project_root, profile_id
    )
    if blocked:
        return blocked
    pipeline = _pipeline_config(cycle_id, project_root, profile_id)
    if pipeline.get("inductive") is not True:
        return _failure(
            _CMD_REVERSE_INDUCTIVE,
            "illegal_transition",
            "reverse-to-inductive requires pipeline.inductive",
        )
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)

    def apply(ledger: dict[str, Any]) -> dict[str, Any]:
        new = step_reverse_to_inductive(ledger)
        slice_dir = (revision_dir / str(new["focus"])).resolve()
        _reset_stage_complete(
            cycle_id,
            project_root,
            profile_id,
            slice_dir,
            init_inductive=True,
        )
        _strip_derived(slice_dir)
        return new

    payload = _with_revision_lock(_CMD_REVERSE_INDUCTIVE, revision_dir, apply)
    if payload.get("ok"):
        try:
            payload["dispatch_input"] = _format_producer_dispatch(
                cycle_id,
                project_root,
                profile_id,
                inductive=True,
                revision_dir=revision_dir,
            )
        except (OSError, ValueError) as exc:
            payload["dispatch_input_error"] = str(exc)
    return payload


def reverse_to_deductive(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(
        _CMD_REVERSE_DEDUCTIVE, cycle_id, project_root, profile_id
    )
    if blocked:
        return blocked
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)

    def apply(ledger: dict[str, Any]) -> dict[str, Any]:
        new = step_reverse_to_deductive(ledger)
        slice_dir = (revision_dir / str(new["focus"])).resolve()
        _reset_stage_complete(
            cycle_id,
            project_root,
            profile_id,
            slice_dir,
            init_inductive=False,
        )
        _strip_derived(slice_dir)
        return new

    payload = _with_revision_lock(_CMD_REVERSE_DEDUCTIVE, revision_dir, apply)
    if payload.get("ok"):
        try:
            payload["dispatch_input"] = _format_producer_dispatch(
                cycle_id,
                project_root,
                profile_id,
                inductive=False,
                revision_dir=revision_dir,
            )
        except (OSError, ValueError) as exc:
            payload["dispatch_input_error"] = str(exc)
    return payload


def reverse_to_writing(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(_CMD_REVERSE_WRITING, cycle_id, project_root, profile_id)
    if blocked:
        return blocked
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)

    def apply(ledger: dict[str, Any]) -> dict[str, Any]:
        new = step_reverse_to_writing(ledger)
        slice_dir = (revision_dir / str(new["focus"])).resolve()
        _clear_stamp(slice_dir, _WRITING_STAMP)
        return new

    payload = _with_revision_lock(_CMD_REVERSE_WRITING, revision_dir, apply)
    if payload.get("ok"):
        try:
            payload["dispatch_input"] = _format_writing_dispatch(
                cycle_id, project_root, profile_id, revision_dir
            )
        except (OSError, ValueError) as exc:
            payload["dispatch_input_error"] = str(exc)
    return payload


def enter_evaluating(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    blocked = _require_working(_CMD_ENTER_EVALUATING, cycle_id, project_root, profile_id)
    if blocked:
        return blocked
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    run_id_holder: dict[str, str] = {}

    def apply(ledger: dict[str, Any]) -> dict[str, Any]:
        state = ledger["by_id"][str(ledger["focus"])]["state"]
        slice_dir = (revision_dir / str(ledger["focus"])).resolve()
        if state == "Writing" and not _has_stamp(slice_dir, _WRITING_STAMP):
            raise IllegalTransition(
                "writing_incomplete",
                "writing complete check failed",
            )
        new = step_enter_evaluating(ledger)
        run_id_holder["eval_run_id"] = _write_eval_run(slice_dir, new)
        return new

    payload = _with_revision_lock(_CMD_ENTER_EVALUATING, revision_dir, apply)
    if payload.get("ok") and run_id_holder.get("eval_run_id"):
        payload["eval_run_id"] = run_id_holder["eval_run_id"]
    return payload


def _eval_exit(
    command: str,
    cycle_id: str,
    project_root: Path,
    profile_id: str,
    *,
    confirm: bool,
    transform: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    if not confirm:
        return _failure(command, "confirmation_required", f"{command} requires --confirm")
    blocked = _require_working(command, cycle_id, project_root, profile_id)
    if blocked:
        return blocked
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)

    def apply(ledger: dict[str, Any]) -> dict[str, Any]:
        slice_dir = (revision_dir / str(ledger["focus"])).resolve()
        meta = _load_eval_run(slice_dir)
        if meta is None:
            raise IllegalTransition("stale_eval", "missing eval_run_id")
        current = ledger_fingerprint(ledger)
        if str(meta.get("ledger_fingerprint", "")) != current:
            raise IllegalTransition("stale_eval", "eval_run_id is stale")
        return transform(ledger)

    return _with_revision_lock(command, revision_dir, apply)


def accept_l(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    confirm: bool = False,
) -> dict[str, Any]:
    return _eval_exit(
        _CMD_ACCEPT,
        cycle_id,
        project_root,
        profile_id,
        confirm=confirm,
        transform=step_accept,
    )


def fix_l(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    confirm: bool = False,
) -> dict[str, Any]:
    return _eval_exit(
        _CMD_FIX,
        cycle_id,
        project_root,
        profile_id,
        confirm=confirm,
        transform=step_fix,
    )


def re_evaluate(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    confirm: bool = False,
) -> dict[str, Any]:
    if not confirm:
        return _failure(
            _CMD_RE_EVALUATE,
            "confirmation_required",
            "re-evaluate requires --confirm",
        )
    blocked = _require_working(_CMD_RE_EVALUATE, cycle_id, project_root, profile_id)
    if blocked:
        return blocked
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    try:
        with revision_lock(revision_dir, exclusive=True):
            ledger = load_l_ledger(revision_dir)
            focus = str(ledger["focus"])
            if ledger["by_id"][focus]["state"] != "Evaluating":
                return _failure(
                    _CMD_RE_EVALUATE,
                    "illegal_transition",
                    "re-evaluate requires Evaluating",
                )
            if ledger["by_id"][focus]["frozen"] is True:
                return _failure(
                    _CMD_RE_EVALUATE,
                    "illegal_transition",
                    f"focus {focus} is frozen",
                )
            slice_dir = (revision_dir / focus).resolve()
            run_id = _write_eval_run(slice_dir, ledger)
            return _success(
                _CMD_RE_EVALUATE,
                state="Evaluating",
                eval_run_id=run_id,
            )
    except LockTimeout:
        return _failure(_CMD_RE_EVALUATE, "lock_timeout", "revision lock timeout")
    except (OSError, ValueError, FileNotFoundError) as exc:
        return _failure(_CMD_RE_EVALUATE, "invalid_ledger", str(exc))


def reopen_current(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    confirm: bool = False,
) -> dict[str, Any]:
    if not confirm:
        return _failure(
            _CMD_REOPEN,
            "confirmation_required",
            "reopen requires --confirm",
        )
    blocked = _require_working(_CMD_REOPEN, cycle_id, project_root, profile_id)
    if blocked:
        return blocked
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    return _with_revision_lock(_CMD_REOPEN, revision_dir, step_reopen)


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Compose single-L step control")
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    sub = parser.add_subparsers(dest="command", required=True)
    for command in (
        _CMD_STATUS,
        _CMD_ENTER_FACT_INTAKE,
        _CMD_COMPLETE_FACT_INTAKE,
        _CMD_ENTER_INDUCTIVE,
        _CMD_COMPLETE_INDUCTIVE,
        _CMD_ENTER_DEDUCTIVE,
        _CMD_COMPLETE_DEDUCTIVE,
        _CMD_ENTER_WRITING,
        _CMD_COMPLETE_WRITING,
        _CMD_ENTER_FREEEDIT,
        _CMD_REVERSE_INDUCTIVE,
        _CMD_REVERSE_DEDUCTIVE,
        _CMD_REVERSE_WRITING,
        _CMD_ENTER_EVALUATING,
    ):
        sub.add_parser(command)
    for command in (_CMD_ACCEPT, _CMD_FIX, _CMD_RE_EVALUATE, _CMD_REOPEN):
        p = sub.add_parser(command)
        p.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    try:
        profile_id = resolve_profile_id(
            project_root=args.project_root.resolve(),
            cycle_id=args.cycle_id.strip(),
        )
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    kwargs = {
        "cycle_id": args.cycle_id.strip(),
        "project_root": args.project_root.resolve(),
        "profile_id": profile_id,
    }
    session_dir = session_state_path(
        kwargs["cycle_id"],
        profile_id,
        kwargs["project_root"],
    ).parent
    confirm = bool(getattr(args, "confirm", False))
    try:
        with session_lock(session_dir, exclusive=False):
            if args.command == _CMD_STATUS:
                result = draft_status(**kwargs)
            elif args.command == _CMD_ENTER_FACT_INTAKE:
                result = enter_fact_intake(**kwargs)
            elif args.command == _CMD_COMPLETE_FACT_INTAKE:
                result = complete_fact_intake(**kwargs)
            elif args.command == _CMD_ENTER_INDUCTIVE:
                result = enter_inductive(**kwargs)
            elif args.command == _CMD_COMPLETE_INDUCTIVE:
                result = complete_inductive(**kwargs)
            elif args.command == _CMD_ENTER_DEDUCTIVE:
                result = enter_deductive(**kwargs)
            elif args.command == _CMD_COMPLETE_DEDUCTIVE:
                result = complete_deductive(**kwargs)
            elif args.command == _CMD_ENTER_WRITING:
                result = enter_writing(**kwargs)
            elif args.command == _CMD_COMPLETE_WRITING:
                result = complete_writing(**kwargs)
            elif args.command == _CMD_ENTER_FREEEDIT:
                result = enter_freeedit(**kwargs)
            elif args.command == _CMD_REVERSE_INDUCTIVE:
                result = reverse_to_inductive(**kwargs)
            elif args.command == _CMD_REVERSE_DEDUCTIVE:
                result = reverse_to_deductive(**kwargs)
            elif args.command == _CMD_REVERSE_WRITING:
                result = reverse_to_writing(**kwargs)
            elif args.command == _CMD_ENTER_EVALUATING:
                result = enter_evaluating(**kwargs)
            elif args.command == _CMD_ACCEPT:
                result = accept_l(**kwargs, confirm=confirm)
            elif args.command == _CMD_FIX:
                result = fix_l(**kwargs, confirm=confirm)
            elif args.command == _CMD_RE_EVALUATE:
                result = re_evaluate(**kwargs, confirm=confirm)
            elif args.command == _CMD_REOPEN:
                result = reopen_current(**kwargs, confirm=confirm)
            else:
                return 1
    except LockTimeout:
        result = _failure(args.command, "lock_timeout", "session lock timeout")
    if result.get("ok") and "dispatch_input" in result:
        print(result["dispatch_input"])
        return 0
    return _emit(result)


def _read_evaluate_round_field(path: Path) -> int | None:
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("evaluate_round:"):
            raw = line.split(":", 1)[1].strip()
            try:
                return int(raw)
            except ValueError:
                return None
    return None


def _allocate_per_l_round(slice_dir: Path) -> int:
    es_path = slice_dir / "evaluate-state.md"
    if not es_path.is_file():
        return 1
    status = ""
    for line in es_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("eval_status:"):
            status = line.split(":", 1)[1].strip()
            break
    current = _read_evaluate_round_field(es_path) or 1
    if status in {"done", "abandoned"}:
        return current + 1
    return current if current >= 1 else 1


def enter_evaluating_state(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    """Ensure focus L is Evaluating; session remains Working."""
    from compose_session import workflow_state_path  # noqa: WPS433
    from l_ledger_schema import focus_state  # noqa: WPS433

    ws_path = workflow_state_path(cycle_id, project_root, profile_id)
    state = load_workflow_state(ws_path)
    current = state["current_state"]
    if current != "Working":
        return {
            "ok": False,
            "current_state": current,
            "transitioned": False,
            "resume": {
                "entry": current,
                "action": f"当前状态是 {current}，需要 Working 才能开始评估当前 L。",
            },
        }
    revision_dir = ws_path.parent
    try:
        ledger = load_l_ledger(revision_dir)
    except (OSError, ValueError, FileNotFoundError) as exc:
        return {
            "ok": False,
            "current_state": current,
            "transitioned": False,
            "error": str(exc),
            "resume": {"entry": current, "action": str(exc)},
        }
    focus = str(ledger["focus"])
    if focus_state(ledger) == "Evaluating":
        evaluate_round = _allocate_per_l_round(revision_dir / focus)
        return {
            "ok": True,
            "current_state": "Working",
            "focus": focus,
            "phase": "evaluating",
            "evaluate_round": evaluate_round,
            "layout": "per-l",
            "transitioned": False,
        }
    result = enter_evaluating(cycle_id, project_root, profile_id=profile_id)
    if not result.get("ok"):
        return {
            "ok": False,
            "current_state": current,
            "transitioned": False,
            "error": result.get("error") or result.get("code") or "enter-evaluating failed",
            "resume": {
                "entry": current,
                "action": str(result.get("error") or "enter-evaluating failed"),
            },
        }
    evaluate_round = _allocate_per_l_round(revision_dir / focus)
    return {
        "ok": True,
        "current_state": "Working",
        "focus": focus,
        "phase": "evaluating",
        "evaluate_round": evaluate_round,
        "layout": "per-l",
        "transitioned": True,
    }


def rollback_evaluating_phase(
    revision_dir: Path,
    *,
    focus: str,
    previous_phase: str = "",
) -> None:
    """Restore a producer phase after a failed first-enter admission.

    ``previous_phase`` is provider-opaque. Compose can only restore Writing or
    FreeEdit; any other token leaves Evaluating and its eval run untouched.
    """
    if previous_phase not in {"Writing", "FreeEdit"}:
        return
    ledger = load_l_ledger(revision_dir)
    if str(ledger["focus"]) != focus:
        return
    try:
        save_l_ledger(
            revision_dir,
            step_abort_evaluating(ledger, previous=previous_phase),
        )
    except IllegalTransition:
        return
    slice_dir = revision_dir / focus
    eval_run = slice_dir / _EVAL_RUN_FILE
    if eval_run.is_file():
        eval_run.unlink()
    staging = slice_dir / ".eval-staging"
    if staging.is_dir():
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(_cli())
