#!/usr/bin/env python3
"""Generic profile-aware L-step control for compose stages (`$L_STEP`)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SECTION.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from compose_session import document_file_path, load_active_doc_for_profile  # noqa: E402
from l_step_progress_schema import (  # noqa: E402
    load_l_step_progress,
    read_current_step,
    resolve_l_step_progress_path_from_cycle,
    save_l_step_progress,
)
from delivered_refs_schema import serialize_delivered_refs  # noqa: E402
from dependency_tree_schema import load_dependency_tree  # noqa: E402
from discussion_pointer_schema import (  # noqa: E402
    active_slice_dir,
    load_discussion_pointer,
    save_discussion_pointer,
)
from facts_schema import facts_path  # noqa: E402
from deductive_gate import evaluate_deductive_gate  # noqa: E402
from writing_compose_validation import validate_writing_artifacts  # noqa: E402
from multi_slice_control import evaluate_split_ready  # noqa: E402
from start_adapter import (  # noqa: E402
    intent_baseline_from_workflow,
    norm_constraint_from_workflow,
    primary_scope_from_workflow,
)
from workflow_common import detect_cycle_type  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, load_profile  # noqa: E402
from workflow_profile_paths import doc_dir, inductive_out_dir  # noqa: E402
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
)

_CMD_BEGIN_INDUCTIVE = "begin-inductive"
_CMD_INDUCTIVE_COMPLETE = "inductive-complete"
_CMD_BEGIN_DEDUCTIVE = "begin-deductive"
_CMD_DEDUCTIVE_COMPLETE = "deductive-complete"
_CMD_BEGIN_WRITING = "begin-writing"
_CMD_WRITING_COMPLETE = "writing-complete"
_CMD_ADVANCE_TO_FREEEDIT = "advance-to-freeedit"
_CMD_STATUS = "status"
_STEP_INDUCTIVE = "Inductive"
_STEP_DEDUCTIVE = "Deductive"
_STEP_WRITTEN = "Written"
_STEP_FREE_EDIT = "FreeEdit"
_INDUCTIVE_SUBDIR = "inductive-scope"
_INDUCTIVE_GATE_STATE_FILE = "inductive-gate-state.json"
_PROVENANCE_GATE_STATE_FILE = "provenance-gate-state.json"


def _success(command: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "command": command}
    payload.update(extra)
    return payload


def _failure(command: str, reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "command": command, "reason": reason}
    payload.update(extra)
    return payload


def _pipeline_config(cycle_id: str, project_root: Path, profile_id: str) -> dict:
    profile = load_profile(profile_id, project_root=project_root, cycle_id=cycle_id)
    return profile.get("pipeline") or {}


def _progress_path(cycle_id: str, project_root: Path, profile_id: str) -> Path:
    return resolve_l_step_progress_path_from_cycle(
        cycle_id,
        project_root,
        profile_id=profile_id,
    )


def _revision_dir(cycle_id: str, project_root: Path, profile_id: str) -> Path:
    active_doc = load_active_doc_for_profile(cycle_id, project_root, profile_id)
    return (project_root / doc_dir(cycle_id, active_doc, profile_id, project_root)).resolve()


def _require_working_session(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
    command: str,
) -> str | None:
    """Return failure reason unless workflow-state is Working and topology locked."""
    _ = command
    ws_path = resolve_workflow_state_path_from_cycle(
        cycle_id, project_root, profile_id=profile_id,
    )
    if not ws_path.is_file():
        return "workflow-state.md not found (run start; complete Split first)"
    try:
        state = load_workflow_state(ws_path)
    except ValueError as exc:
        return str(exc)
    current = str(state.get("current_state", "")).strip()
    if current == "Split":
        return (
            "session is still Split; run split-complete after locking topology "
            "(single-req = explicit L1 tree)"
        )
    if current != "Working":
        return f"session current_state is {current!r} (expected Working)"
    ok, err, _ = evaluate_split_ready(ws_path.parent)
    if not ok:
        return (
            "locked split topology required before Working producer "
            f"({err or 'check-split-ready failed'})"
        )
    return None


def _ensure_focus_phase_in_progress(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> str | None:
    """pending → in_progress on focus when beginning intake producer. None = ok."""
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    try:
        tree = load_dependency_tree(revision_dir)
        pointer = load_discussion_pointer(revision_dir)
    except (FileNotFoundError, ValueError, OSError) as exc:
        return str(exc)
    focus = str(pointer["focus"])
    cell = pointer["by_id"][focus]
    phase = str(cell.get("phase") or "pending")
    if phase == "accepted":
        return f"focus {focus!r} is accepted; demote or switch before producer"
    if phase == "evaluating":
        return f"focus {focus!r} is evaluating; Fix L before producer"
    if phase == "pending":
        cell["phase"] = "in_progress"
        try:
            save_discussion_pointer(revision_dir, pointer, tree=tree)
        except ValueError as exc:
            return str(exc)
    return None


def _scope_doc(cycle_id: str, project_root: Path, profile_id: str) -> Path:
    init_ref = primary_scope_from_workflow(cycle_id, project_root, profile_id)
    if init_ref is None:
        raise ValueError("no scope ref available for Writing")
    scope_path = Path(init_ref.path).resolve()
    if not scope_path.is_file():
        raise ValueError(f"scope doc not found: {scope_path}")
    return scope_path


def _inductive_out_dir(cycle_id: str, project_root: Path, profile_id: str) -> Path:
    return (project_root / inductive_out_dir(cycle_id, profile_id, project_root)).resolve()


def _inductive_dir(cycle_id: str, project_root: Path, profile_id: str) -> Path:
    return _inductive_out_dir(cycle_id, project_root, profile_id) / _INDUCTIVE_SUBDIR


def _inductive_g4_closed(cycle_id: str, project_root: Path, profile_id: str) -> bool:
    gate_state_path = (
        _inductive_out_dir(cycle_id, project_root, profile_id) / _INDUCTIVE_GATE_STATE_FILE
    )
    if not gate_state_path.exists():
        return False
    try:
        data = json.loads(gate_state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return str(data.get("gates", {}).get("G4", {}).get("status", "")).lower() == "closed"


def _inductive_g5_closed(cycle_id: str, project_root: Path, profile_id: str) -> bool:
    gate_state_path = (
        _inductive_out_dir(cycle_id, project_root, profile_id) / _PROVENANCE_GATE_STATE_FILE
    )
    if not gate_state_path.exists():
        return False
    try:
        data = json.loads(gate_state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return str(data.get("status", "")).lower() == "closed"


def _inductive_spine_gate_failure(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> str | None:
    if not _inductive_g4_closed(cycle_id, project_root, profile_id):
        return "inductive Gate 4 not closed"
    if not _inductive_g5_closed(cycle_id, project_root, profile_id):
        return "inductive Gate 5 not closed"
    return None


def _inductive_scope_ref_path(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> Path:
    """Resolve inductive ``$SCOPE_REF`` from the L-local source_path mirror."""
    from scope_package_convert import (  # noqa: WPS433
        ScopePackageAntiseepError,
        focus_seed_source_path,
        revision_uses_scope_package,
    )
    from scope_package_schema import is_scope_package_path  # noqa: WPS433

    scope_path = _scope_doc(cycle_id, project_root, profile_id)
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    if revision_uses_scope_package(revision_dir) or is_scope_package_path(scope_path):
        try:
            fact = focus_seed_source_path(revision_dir)
        except ScopePackageAntiseepError:
            raise
        return Path(fact)
    return scope_path


def _format_inductive_dispatch_input(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> str:
    intent_refs = intent_baseline_from_workflow(cycle_id, project_root, profile_id)
    norm_refs = norm_constraint_from_workflow(cycle_id, project_root, profile_id)
    scope_ref = _inductive_scope_ref_path(cycle_id, project_root, profile_id)
    lines = [
        f"COMPOSE_PROFILE:      {profile_id}",
        f"CYCLE_ID:             {cycle_id}",
        f"SCOPE_REF:            {scope_ref.as_posix()}",
        f"INTENT_BASELINE_REFS: {serialize_delivered_refs(intent_refs)}",
        f"NORM_CONSTRAINT_REFS: {serialize_delivered_refs(norm_refs)}",
        f"INDUCTIVE_OUT_DIR:    {_inductive_out_dir(cycle_id, project_root, profile_id).as_posix()}",
    ]
    return "\n".join(lines)


def _intake_source_path_for_focus(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
    scope_path: Path,
) -> Path:
    """Resolve the current L's format-neutral fact-intake SoT path."""
    from compose_package_schema import (  # noqa: WPS433
        is_compose_package_path,
        load_compose_package,
        resolve_focus_doc_path,
    )
    from discussion_pointer_schema import load_discussion_pointer  # noqa: WPS433
    from scope_package_convert import (  # noqa: WPS433
        focus_seed_source_path,
        revision_uses_scope_package,
    )
    from scope_package_schema import is_scope_package_path  # noqa: WPS433

    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    if revision_uses_scope_package(revision_dir) or is_scope_package_path(scope_path):
        return Path(focus_seed_source_path(revision_dir))
    if not is_compose_package_path(scope_path):
        return scope_path
    package = load_compose_package(scope_path)
    focus = str(
        load_discussion_pointer(revision_dir).get(
            "focus", ""
        )
    ).strip()
    if not focus:
        raise ValueError("discussion-pointer focus missing for SOURCE_PATH")
    return resolve_focus_doc_path(package, focus, package_path=scope_path)


def _format_deductive_dispatch_input(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> str:
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    pipeline = _pipeline_config(cycle_id, project_root, profile_id)
    code_grounding = bool(pipeline.get("code_grounding"))
    scope_path = _scope_doc(cycle_id, project_root, profile_id)
    intent_refs = intent_baseline_from_workflow(cycle_id, project_root, profile_id)
    norm_refs = norm_constraint_from_workflow(cycle_id, project_root, profile_id)
    lines = [
        f"COMPOSE_PROFILE:      {profile_id}",
        f"CYCLE_ID:             {cycle_id}",
        f"SCOPE_REF:            {scope_path.as_posix()}",
        f"INTENT_BASELINE_REFS: {serialize_delivered_refs(intent_refs)}",
        f"NORM_CONSTRAINT_REFS: {serialize_delivered_refs(norm_refs)}",
        f"DEDUCTIVE_OUT_DIR:    {revision_dir.as_posix()}",
        f"CODE_GROUNDING:       {str(code_grounding).lower()}",
    ]
    source_path = _intake_source_path_for_focus(
        cycle_id, project_root, profile_id, scope_path
    )
    source = source_path.as_posix()
    lines.append(f"SOURCE_PATH:          {source}")
    # Retired alias — same path as SOURCE_PATH (fact-intake SoT).
    lines.append(f"ATOMIZE_SOURCE_PATH:  {source}")
    return "\n".join(lines)


def _deductive_gate_failure(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> str | None:
    return evaluate_deductive_gate(
        _revision_dir(cycle_id, project_root, profile_id),
    )


def _format_init_dispatch_input(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> str:
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    output_doc = document_file_path(cycle_id, project_root, profile_id)
    lines = [
        f"REVISION_DIR:         {revision_dir.as_posix()}",
        f"SCOPE_REF_PATH:       {_scope_doc(cycle_id, project_root, profile_id).as_posix()}",
        f"OUTPUT_DOC_PATH:      {output_doc.resolve().as_posix()}",
        f"COMPOSE_PROFILE:      {profile_id}",
        f"CYCLE_TYPE:           {detect_cycle_type(cycle_id)}",
        f"CYCLE_ID:             {cycle_id}",
    ]
    # K4: Writing consumes discovery-written _facts.json — never advertise
    # INDUCTIVE_DIR as if Writing still reads decisions[] / projection here.
    return "\n".join(lines)


def begin_inductive(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    if _pipeline_config(cycle_id, project_root, profile_id).get("inductive") is not True:
        return _failure(_CMD_BEGIN_INDUCTIVE, "pipeline.inductive is false for this profile")

    session_err = _require_working_session(
        cycle_id, project_root, profile_id, _CMD_BEGIN_INDUCTIVE,
    )
    if session_err:
        return _failure(_CMD_BEGIN_INDUCTIVE, session_err)
    phase_err = _ensure_focus_phase_in_progress(cycle_id, project_root, profile_id)
    if phase_err:
        return _failure(_CMD_BEGIN_INDUCTIVE, phase_err)

    progress_path = _progress_path(cycle_id, project_root, profile_id)
    if progress_path.exists():
        step = read_current_step(progress_path)
        if step not in (None, _STEP_INDUCTIVE):
            return _failure(
                _CMD_BEGIN_INDUCTIVE,
                f"cannot start Inductive: current_step is {step!r} (expected absent or Inductive)",
                current_step=step,
            )
    from scope_package_convert import ScopePackageAntiseepError  # noqa: WPS433

    try:
        dispatch_input = _format_inductive_dispatch_input(
            cycle_id, project_root, profile_id,
        )
    except (ScopePackageAntiseepError, ValueError) as exc:
        return _failure(_CMD_BEGIN_INDUCTIVE, str(exc))
    save_l_step_progress(
        progress_path,
        {"version": "1", "cycle_id": cycle_id, "current_step": _STEP_INDUCTIVE},
        profile_id=profile_id,
        project_root=project_root,
        cycle_id=cycle_id,
        merge=False,
    )
    return _success(
        _CMD_BEGIN_INDUCTIVE,
        current_step=_STEP_INDUCTIVE,
        dispatch_input=dispatch_input,
    )


def inductive_complete(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    if _pipeline_config(cycle_id, project_root, profile_id).get("inductive") is not True:
        return _failure(_CMD_INDUCTIVE_COMPLETE, "pipeline.inductive is false for this profile")
    progress_path = _progress_path(cycle_id, project_root, profile_id)
    if not progress_path.exists():
        return _failure(_CMD_INDUCTIVE_COMPLETE, "l-step-progress.md not found")
    step = read_current_step(progress_path)
    if step != _STEP_INDUCTIVE:
        return _failure(
            _CMD_INDUCTIVE_COMPLETE,
            f"cannot complete Inductive: current_step is {step!r} (expected Inductive)",
            current_step=step,
        )
    gate_reason = _inductive_spine_gate_failure(cycle_id, project_root, profile_id)
    if gate_reason:
        return _failure(_CMD_INDUCTIVE_COMPLETE, gate_reason)
    inductive_dir = _inductive_dir(cycle_id, project_root, profile_id)
    section_files = (
        sorted(p.name for p in inductive_dir.glob("*.json") if p.name != "_index.json")
        if inductive_dir.is_dir()
        else []
    )
    return _success(
        _CMD_INDUCTIVE_COMPLETE,
        current_step=_STEP_INDUCTIVE,
        inductive_dir=inductive_dir.as_posix(),
        section_files=section_files,
    )


def begin_deductive(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    if _pipeline_config(cycle_id, project_root, profile_id).get("inductive") is True:
        return _failure(
            _CMD_BEGIN_DEDUCTIVE,
            "pipeline.inductive is true — use begin-inductive",
        )

    session_err = _require_working_session(
        cycle_id, project_root, profile_id, _CMD_BEGIN_DEDUCTIVE,
    )
    if session_err:
        return _failure(_CMD_BEGIN_DEDUCTIVE, session_err)
    phase_err = _ensure_focus_phase_in_progress(cycle_id, project_root, profile_id)
    if phase_err:
        return _failure(_CMD_BEGIN_DEDUCTIVE, phase_err)

    progress_path = _progress_path(cycle_id, project_root, profile_id)
    if progress_path.exists():
        step = read_current_step(progress_path)
        if step not in (None, _STEP_DEDUCTIVE):
            return _failure(
                _CMD_BEGIN_DEDUCTIVE,
                f"cannot start Deductive: current_step is {step!r} "
                "(expected absent or Deductive)",
                current_step=step,
            )
    dispatch_input = _format_deductive_dispatch_input(
        cycle_id, project_root, profile_id,
    )
    save_l_step_progress(
        progress_path,
        {"version": "1", "cycle_id": cycle_id, "current_step": _STEP_DEDUCTIVE},
        profile_id=profile_id,
        project_root=project_root,
        cycle_id=cycle_id,
        merge=False,
    )
    return _success(
        _CMD_BEGIN_DEDUCTIVE,
        current_step=_STEP_DEDUCTIVE,
        dispatch_input=dispatch_input,
    )


def deductive_complete(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    if _pipeline_config(cycle_id, project_root, profile_id).get("inductive") is True:
        return _failure(
            _CMD_DEDUCTIVE_COMPLETE,
            "pipeline.inductive is true — use inductive-complete",
        )
    progress_path = _progress_path(cycle_id, project_root, profile_id)
    if not progress_path.exists():
        return _failure(_CMD_DEDUCTIVE_COMPLETE, "l-step-progress.md not found")
    step = read_current_step(progress_path)
    if step != _STEP_DEDUCTIVE:
        return _failure(
            _CMD_DEDUCTIVE_COMPLETE,
            f"cannot complete Deductive: current_step is {step!r} (expected Deductive)",
            current_step=step,
        )
    gate_reason = _deductive_gate_failure(cycle_id, project_root, profile_id)
    if gate_reason:
        return _failure(_CMD_DEDUCTIVE_COMPLETE, gate_reason)
    rev = _revision_dir(cycle_id, project_root, profile_id)
    slice_dir = active_slice_dir(rev)
    return _success(
        _CMD_DEDUCTIVE_COMPLETE,
        current_step=_STEP_DEDUCTIVE,
        revision_dir=rev.as_posix(),
        facts_path=facts_path(slice_dir).as_posix(),
    )


def begin_writing(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    progress_path = _progress_path(cycle_id, project_root, profile_id)
    pipeline = _pipeline_config(cycle_id, project_root, profile_id)
    step = read_current_step(progress_path)
    if pipeline.get("inductive") is True:
        if step not in (_STEP_INDUCTIVE, _STEP_WRITTEN):
            return _failure(
                _CMD_BEGIN_WRITING,
                "cannot start Writing: Inductive not run",
                current_step=step,
            )
        if step == _STEP_INDUCTIVE:
            gate_reason = _inductive_spine_gate_failure(
                cycle_id,
                project_root,
                profile_id,
            )
            if gate_reason:
                return _failure(
                    _CMD_BEGIN_WRITING,
                    f"cannot start Writing: {gate_reason}",
                    current_step=step,
                )
        rev = _revision_dir(cycle_id, project_root, profile_id)
        path = facts_path(active_slice_dir(rev))
        if not path.is_file():
            return _failure(
                _CMD_BEGIN_WRITING,
                "cannot start Writing: _facts.json missing — seed/settle "
                "during inductive must have written _facts.json "
                f"(expected {path.as_posix()})",
                current_step=step,
            )
    else:
        if step not in (_STEP_DEDUCTIVE, _STEP_WRITTEN):
            return _failure(
                _CMD_BEGIN_WRITING,
                "cannot start Writing: Deductive not run",
                current_step=step,
            )
        if step == _STEP_DEDUCTIVE:
            gate_reason = _deductive_gate_failure(cycle_id, project_root, profile_id)
            if gate_reason:
                return _failure(
                    _CMD_BEGIN_WRITING,
                    f"cannot start Writing: {gate_reason}",
                    current_step=step,
                )
    # P4.convert (C1=A): when $SCOPE_REF is scope-package, ensure once (or verify).
    from scope_package_convert import (  # noqa: WPS433
        ScopePackageConvertError,
        ensure_scope_package_convert,
    )
    from scope_package_schema import is_scope_package_path  # noqa: WPS433

    try:
        scope_doc = _scope_doc(cycle_id, project_root, profile_id)
    except ValueError as exc:
        return _failure(_CMD_BEGIN_WRITING, str(exc), current_step=step)
    if is_scope_package_path(scope_doc):
        try:
            ensure_scope_package_convert(
                _revision_dir(cycle_id, project_root, profile_id),
                scope_package_path=scope_doc,
            )
        except ScopePackageConvertError as exc:
            return _failure(
                _CMD_BEGIN_WRITING,
                f"scope-package convert: {exc}",
                current_step=step,
            )

    return _success(
        _CMD_BEGIN_WRITING,
        current_step=step,
        dispatch_input=_format_init_dispatch_input(cycle_id, project_root, profile_id),
    )


def writing_complete(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    progress_path = _progress_path(cycle_id, project_root, profile_id)
    seed_error = validate_writing_artifacts(
        _revision_dir(cycle_id, project_root, profile_id),
        document_file_path(cycle_id, project_root, profile_id),
        project_root,
        profile_id,
    )
    if seed_error:
        return _failure(_CMD_WRITING_COMPLETE, seed_error)
    if progress_path.exists():
        step = read_current_step(progress_path)
        if step not in (
            None,
            _STEP_WRITTEN,
            _STEP_INDUCTIVE,
            _STEP_DEDUCTIVE,
        ):
            return _failure(
                _CMD_WRITING_COMPLETE,
                f"l-step-progress already at {step!r}; cannot re-initialize",
                current_step=step,
            )
    save_l_step_progress(
        progress_path,
        {"version": "1", "cycle_id": cycle_id, "current_step": _STEP_WRITTEN},
        profile_id=profile_id,
        project_root=project_root,
        cycle_id=cycle_id,
        merge=False,
    )
    return _success(_CMD_WRITING_COMPLETE, current_step=_STEP_WRITTEN)


def advance_to_freeedit(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    if _pipeline_config(cycle_id, project_root, profile_id).get("freeedit") is not True:
        return _failure(_CMD_ADVANCE_TO_FREEEDIT, "pipeline.freeedit is false for this profile")
    progress_path = _progress_path(cycle_id, project_root, profile_id)
    if not progress_path.exists():
        return _failure(_CMD_ADVANCE_TO_FREEEDIT, "l-step-progress.md not found")
    step = read_current_step(progress_path)
    if step == _STEP_FREE_EDIT:
        return _success(_CMD_ADVANCE_TO_FREEEDIT, current_step=_STEP_FREE_EDIT)
    if step != _STEP_WRITTEN:
        return _failure(
            _CMD_ADVANCE_TO_FREEEDIT,
            f"cannot advance to FreeEdit: current_step is {step!r} (expected Written)",
            current_step=step,
        )
    save_l_step_progress(
        progress_path,
        {"version": "1", "cycle_id": cycle_id, "current_step": _STEP_FREE_EDIT},
        profile_id=profile_id,
        project_root=project_root,
        cycle_id=cycle_id,
        merge=False,
    )
    return _success(_CMD_ADVANCE_TO_FREEEDIT, current_step=_STEP_FREE_EDIT)


def draft_status(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    progress_path = _progress_path(cycle_id, project_root, profile_id)
    if not progress_path.exists():
        return _failure(_CMD_STATUS, "l-step-progress.md not found")
    data = load_l_step_progress(
        progress_path,
        profile_id=profile_id,
        project_root=project_root,
        cycle_id=cycle_id,
    )
    return _success(
        _CMD_STATUS,
        current_step=data.get("current_step"),
        cycle_id=data.get("cycle_id"),
    )


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _cli() -> int:
    parser = argparse.ArgumentParser(description="generic compose draft control")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--profile", default=DEFAULT_COMPOSE_PROFILE_ID)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in (
        _CMD_BEGIN_INDUCTIVE,
        _CMD_INDUCTIVE_COMPLETE,
        _CMD_BEGIN_DEDUCTIVE,
        _CMD_DEDUCTIVE_COMPLETE,
        _CMD_BEGIN_WRITING,
        _CMD_WRITING_COMPLETE,
        _CMD_ADVANCE_TO_FREEEDIT,
        _CMD_STATUS,
    ):
        sub.add_parser(command)
    args = parser.parse_args()
    kwargs = {
        "cycle_id": args.cycle_id.strip(),
        "project_root": args.project_root.resolve(),
        "profile_id": args.profile.strip(),
    }
    try:
        if args.command == _CMD_BEGIN_INDUCTIVE:
            result = begin_inductive(**kwargs)
        elif args.command == _CMD_INDUCTIVE_COMPLETE:
            result = inductive_complete(**kwargs)
        elif args.command == _CMD_BEGIN_DEDUCTIVE:
            result = begin_deductive(**kwargs)
        elif args.command == _CMD_DEDUCTIVE_COMPLETE:
            result = deductive_complete(**kwargs)
        elif args.command == _CMD_BEGIN_WRITING:
            result = begin_writing(**kwargs)
        elif args.command == _CMD_WRITING_COMPLETE:
            result = writing_complete(**kwargs)
        elif args.command == _CMD_ADVANCE_TO_FREEEDIT:
            result = advance_to_freeedit(**kwargs)
        elif args.command == _CMD_STATUS:
            result = draft_status(**kwargs)
        else:
            return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if result.get("ok") and "dispatch_input" in result:
        print(result["dispatch_input"])
        return 0
    return _emit(result)


if __name__ == "__main__":
    raise SystemExit(_cli())
