#!/usr/bin/env python3
"""Generic profile-aware draft control for compose stages."""

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
from drafting_progress_schema import (  # noqa: E402
    load_drafting_progress,
    read_current_step,
    resolve_drafting_progress_path_from_cycle,
    save_drafting_progress,
)
from init_compose_validation import validate_init_artifacts  # noqa: E402
from start_adapter import primary_scope_from_workflow  # noqa: E402
from workflow_common import detect_cycle_type  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, load_profile  # noqa: E402
from workflow_profile_paths import doc_dir, session_base_dir  # noqa: E402

_CMD_BEGIN_INDUCTIVE = "begin-inductive"
_CMD_INDUCTIVE_COMPLETE = "inductive-complete"
_CMD_BEGIN_INIT = "begin-init"
_CMD_INIT_COMPLETE = "init-complete"
_CMD_ADVANCE_TO_FREEEDIT = "advance-to-freeedit"
_CMD_STATUS = "status"
_STEP_INDUCTIVE = "Inductive"
_STEP_INITIALIZED = "Initialized"
_STEP_FREE_EDIT = "FreeEdit"
_INDUCTIVE_SUBDIR = "inductive-scope"
_INDUCTIVE_GATE_STATE_FILE = "inductive-gate-state.json"


def _success(command: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "command": command}
    payload.update(extra)
    return payload


def _failure(command: str, reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "command": command, "reason": reason}
    payload.update(extra)
    return payload


def _drafting_config(cycle_id: str, project_root: Path, profile_id: str) -> dict:
    profile = load_profile(profile_id, project_root=project_root, cycle_id=cycle_id)
    return profile.get("drafting") or {}


def _progress_path(cycle_id: str, project_root: Path, profile_id: str) -> Path:
    return resolve_drafting_progress_path_from_cycle(
        cycle_id,
        project_root,
        profile_id=profile_id,
    )


def _revision_dir(cycle_id: str, project_root: Path, profile_id: str) -> Path:
    active_doc = load_active_doc_for_profile(cycle_id, project_root, profile_id)
    return (project_root / doc_dir(cycle_id, active_doc, profile_id, project_root)).resolve()


def _scope_doc(cycle_id: str, project_root: Path, profile_id: str) -> Path:
    init_ref = primary_scope_from_workflow(cycle_id, project_root, profile_id)
    if init_ref is None:
        raise ValueError("no scope ref available for Initializing")
    scope_path = Path(init_ref.path).resolve()
    if not scope_path.is_file():
        raise ValueError(f"scope doc not found: {scope_path}")
    return scope_path


def _inductive_out_dir(cycle_id: str, project_root: Path, profile_id: str) -> Path:
    return (project_root / session_base_dir(cycle_id, profile_id, project_root)).resolve()


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


def _format_inductive_dispatch_input(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> str:
    lines = [
        f"COMPOSE_PROFILE:      {profile_id}",
        f"CYCLE_ID:             {cycle_id}",
        f"SCOPE_DOC:            {_scope_doc(cycle_id, project_root, profile_id).as_posix()}",
        f"INDUCTIVE_OUT_DIR:    {_inductive_out_dir(cycle_id, project_root, profile_id).as_posix()}",
    ]
    return "\n".join(lines)


def _format_init_dispatch_input(
    cycle_id: str,
    project_root: Path,
    profile_id: str,
) -> str:
    revision_dir = _revision_dir(cycle_id, project_root, profile_id)
    output_doc = document_file_path(cycle_id, project_root, profile_id)
    lines = [
        f"REVISION_DIR:         {revision_dir.as_posix()}",
        f"SCOPE_DOC_PATH:       {_scope_doc(cycle_id, project_root, profile_id).as_posix()}",
        f"OUTPUT_DOC_PATH:      {output_doc.resolve().as_posix()}",
        f"COMPOSE_PROFILE:      {profile_id}",
        f"CYCLE_TYPE:           {detect_cycle_type(cycle_id)}",
        f"CYCLE_ID:             {cycle_id}",
    ]
    inductive_dir = _inductive_dir(cycle_id, project_root, profile_id)
    if inductive_dir.is_dir():
        lines.append(f"INDUCTIVE_DIR:        {inductive_dir.as_posix()}")
    return "\n".join(lines)


def begin_inductive(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    if _drafting_config(cycle_id, project_root, profile_id).get("inductive") is not True:
        return _failure(_CMD_BEGIN_INDUCTIVE, "drafting.inductive is false for this profile")

    progress_path = _progress_path(cycle_id, project_root, profile_id)
    if progress_path.exists():
        step = read_current_step(progress_path)
        if step not in (None, _STEP_INDUCTIVE):
            return _failure(
                _CMD_BEGIN_INDUCTIVE,
                f"cannot start Inductive: current_step is {step!r} (expected absent or Inductive)",
                current_step=step,
            )
    dispatch_input = _format_inductive_dispatch_input(cycle_id, project_root, profile_id)
    save_drafting_progress(
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
    if _drafting_config(cycle_id, project_root, profile_id).get("inductive") is not True:
        return _failure(_CMD_INDUCTIVE_COMPLETE, "drafting.inductive is false for this profile")
    progress_path = _progress_path(cycle_id, project_root, profile_id)
    if not progress_path.exists():
        return _failure(_CMD_INDUCTIVE_COMPLETE, "drafting-progress.md not found")
    step = read_current_step(progress_path)
    if step != _STEP_INDUCTIVE:
        return _failure(
            _CMD_INDUCTIVE_COMPLETE,
            f"cannot complete Inductive: current_step is {step!r} (expected Inductive)",
            current_step=step,
        )
    if not _inductive_g4_closed(cycle_id, project_root, profile_id):
        return _failure(_CMD_INDUCTIVE_COMPLETE, "inductive Gate 4 not closed")
    inductive_dir = _inductive_dir(cycle_id, project_root, profile_id)
    section_files = sorted(p.name for p in inductive_dir.glob("*.md")) if inductive_dir.is_dir() else []
    return _success(
        _CMD_INDUCTIVE_COMPLETE,
        current_step=_STEP_INDUCTIVE,
        inductive_dir=inductive_dir.as_posix(),
        section_files=section_files,
    )


def begin_init(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    progress_path = _progress_path(cycle_id, project_root, profile_id)
    drafting = _drafting_config(cycle_id, project_root, profile_id)
    step = read_current_step(progress_path)
    if drafting.get("inductive") is True:
        if step not in (_STEP_INDUCTIVE, _STEP_INITIALIZED):
            return _failure(
                _CMD_BEGIN_INIT,
                "cannot start Initializing: Inductive not run",
                current_step=step,
            )
        if step == _STEP_INDUCTIVE and not _inductive_g4_closed(cycle_id, project_root, profile_id):
            return _failure(
                _CMD_BEGIN_INIT,
                "cannot start Initializing: inductive Gate 4 not closed",
                current_step=step,
            )
    elif step not in (None, _STEP_INITIALIZED):
        return _failure(
            _CMD_BEGIN_INIT,
            f"cannot start Initializing: current_step is {step!r} (expected absent or Initialized)",
            current_step=step,
        )
    return _success(
        _CMD_BEGIN_INIT,
        current_step=step,
        dispatch_input=_format_init_dispatch_input(cycle_id, project_root, profile_id),
    )


def init_complete(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    progress_path = _progress_path(cycle_id, project_root, profile_id)
    seed_error = validate_init_artifacts(
        _revision_dir(cycle_id, project_root, profile_id),
        document_file_path(cycle_id, project_root, profile_id),
        project_root,
        profile_id,
    )
    if seed_error:
        return _failure(_CMD_INIT_COMPLETE, seed_error)
    if progress_path.exists():
        step = read_current_step(progress_path)
        if step not in (None, _STEP_INITIALIZED, _STEP_INDUCTIVE):
            return _failure(
                _CMD_INIT_COMPLETE,
                f"drafting-progress already at {step!r}; cannot re-initialize",
                current_step=step,
            )
    save_drafting_progress(
        progress_path,
        {"version": "1", "cycle_id": cycle_id, "current_step": _STEP_INITIALIZED},
        profile_id=profile_id,
        project_root=project_root,
        cycle_id=cycle_id,
        merge=False,
    )
    return _success(_CMD_INIT_COMPLETE, current_step=_STEP_INITIALIZED)


def advance_to_freeedit(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> dict[str, Any]:
    if _drafting_config(cycle_id, project_root, profile_id).get("freeedit") is not True:
        return _failure(_CMD_ADVANCE_TO_FREEEDIT, "drafting.freeedit is false for this profile")
    progress_path = _progress_path(cycle_id, project_root, profile_id)
    if not progress_path.exists():
        return _failure(_CMD_ADVANCE_TO_FREEEDIT, "drafting-progress.md not found")
    step = read_current_step(progress_path)
    if step == _STEP_FREE_EDIT:
        return _success(_CMD_ADVANCE_TO_FREEEDIT, current_step=_STEP_FREE_EDIT)
    if step != _STEP_INITIALIZED:
        return _failure(
            _CMD_ADVANCE_TO_FREEEDIT,
            f"cannot advance to FreeEdit: current_step is {step!r} (expected Initialized)",
            current_step=step,
        )
    save_drafting_progress(
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
        return _failure(_CMD_STATUS, "drafting-progress.md not found")
    data = load_drafting_progress(
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
        _CMD_BEGIN_INIT,
        _CMD_INIT_COMPLETE,
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
        elif args.command == _CMD_BEGIN_INIT:
            result = begin_init(**kwargs)
        elif args.command == _CMD_INIT_COMPLETE:
            result = init_complete(**kwargs)
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
