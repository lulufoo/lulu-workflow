#!/usr/bin/env python3
"""Draft control for tech-plan orchestrator.

Subcommands:
    begin-init            Check whether Initializing can start; on success print
                          initializing-runner ## Input block (plain text)
    init-complete         Validate composed tech-doc (all sections non-empty) and write Ready
    advance-to-freeedit   Transition Ready -> FreeEdit (Round removed from tech-plan)
    status                Read drafting-progress snapshot (read-only)

Deprecated (return failure; Round removed from tech-plan):
    begin-round           Was: Transition Ready -> RoundIteration (round 1)
    advance-round         Was: Increment round while in RoundIteration
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts"
_CORE = _KERNEL_SCRIPTS / "core"
_SECTION = _KERNEL_SCRIPTS / "section"
_DRAFTING = Path(__file__).resolve().parent
_START = _DRAFTING.parent / "start"
for p in (_KERNEL_SCRIPTS, _CORE, _SECTION, _DRAFTING, _START):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from tech_plan_drafting_progress_schema import (  # noqa: E402
    load_drafting_progress,
    read_current_step,
    resolve_drafting_progress_path_from_cycle,
    save_drafting_progress,
)
from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import detect_cycle_type  # noqa: E402
from workflow_profile_paths import doc_dir, document_path  # noqa: E402
from tech_plan_start_adapter import TechPlanStartAdapter  # noqa: E402

_CMD_BEGIN_INIT = "begin-init"
_PROFILE_ID = "tech-plan"
_CMD_INIT_COMPLETE = "init-complete"
_CMD_BEGIN_ROUND = "begin-round"
_CMD_ADVANCE_ROUND = "advance-round"
_CMD_ADVANCE_TO_FREEEDIT = "advance-to-freeedit"
_CMD_STATUS = "status"
_STEP_READY = "Ready"
_STEP_ROUND = "RoundIteration"
_STEP_FREE_EDIT = "FreeEdit"


def _compose_doc_path(cycle_id: str, project_root: Path) -> Path:
    active_doc = load_active_doc_from_cycle(cycle_id, project_root, profile_id=_PROFILE_ID)
    return project_root / document_path(cycle_id, active_doc, _PROFILE_ID, project_root)


def _success(command: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "command": command}
    payload.update(extra)
    return payload


def _failure(command: str, reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "command": command, "reason": reason}
    payload.update(extra)
    return payload


def _format_init_dispatch_input(
    *,
    revision_dir: Path,
    scope_doc: Path,
    output_doc: Path,
    cycle_type: str,
    cycle_id: str,
) -> str:
    lines = [
        f"REVISION_DIR:         {revision_dir.resolve().as_posix()}",
        f"SCOPE_DOC_PATH:       {scope_doc.resolve().as_posix()}",
        f"OUTPUT_DOC_PATH:      {output_doc.resolve().as_posix()}",
        f"COMPOSE_PROFILE:      {_PROFILE_ID}",
        f"CYCLE_TYPE:           {cycle_type}",
        f"CYCLE_ID:             {cycle_id}",
    ]
    return "\n".join(lines)


def _init_dispatch_input(cycle_id: str, project_root: Path) -> str:
    active_doc = load_active_doc_from_cycle(cycle_id, project_root, profile_id=_PROFILE_ID)
    revision_dir = project_root / doc_dir(cycle_id, active_doc, _PROFILE_ID, project_root)
    output_doc = _compose_doc_path(cycle_id, project_root)
    adapter = TechPlanStartAdapter()
    init_ref = adapter.delivered_ref_for_init(cycle_id, project_root)
    if init_ref is None:
        raise ValueError("no scope ref available for Initializing")
    scope_path = Path(init_ref.path).resolve()
    if not scope_path.is_file():
        raise ValueError(f"scope doc not found: {scope_path}")
    return _format_init_dispatch_input(
        revision_dir=revision_dir,
        scope_doc=scope_path,
        output_doc=output_doc,
        cycle_type=detect_cycle_type(cycle_id),
        cycle_id=cycle_id,
    )


def _revision_dir(cycle_id: str, project_root: Path) -> Path:
    active_doc = load_active_doc_from_cycle(cycle_id, project_root, profile_id=_PROFILE_ID)
    return (project_root / doc_dir(cycle_id, active_doc, _PROFILE_ID, project_root)).resolve()


def _validate_init_complete(cycle_id: str, project_root: Path) -> str | None:
    from init_compose_validation import validate_init_artifacts  # noqa: WPS433

    return validate_init_artifacts(
        _revision_dir(cycle_id, project_root),
        _compose_doc_path(cycle_id, project_root),
        project_root,
        _PROFILE_ID,
    )


def begin_init(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    dispatch_input = _init_dispatch_input(cycle_id, project_root)
    if not progress_path.exists():
        return _success(
            _CMD_BEGIN_INIT,
            current_step=None,
            dispatch_input=dispatch_input,
        )

    step = read_current_step(progress_path)
    if step == _STEP_READY:
        return _success(
            _CMD_BEGIN_INIT,
            current_step=_STEP_READY,
            dispatch_input=dispatch_input,
        )

    return _failure(
        _CMD_BEGIN_INIT,
        f"cannot start Initializing: current_step is {step!r} (expected absent or Ready)",
        current_step=step,
    )


def init_complete(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    compose_doc = _compose_doc_path(cycle_id, project_root)

    seed_error = _validate_init_complete(cycle_id, project_root)
    if seed_error:
        return _failure(_CMD_INIT_COMPLETE, seed_error)

    if progress_path.exists():
        step = read_current_step(progress_path)
        if step not in (None, _STEP_READY):
            return _failure(
                _CMD_INIT_COMPLETE,
                f"drafting-progress already at {step!r}; cannot re-initialize",
                current_step=step,
            )
        existing = load_drafting_progress(progress_path)
        if (
            existing.get("current_step") == _STEP_READY
            and existing.get("cycle_id") == cycle_id
        ):
            return _success(_CMD_INIT_COMPLETE, current_step=_STEP_READY)

    save_drafting_progress(
        progress_path,
        {
            "version": "1",
            "cycle_id": cycle_id,
            "current_step": _STEP_READY,
        },
        merge=False,
    )
    return _success(_CMD_INIT_COMPLETE, current_step=_STEP_READY)


def begin_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    return _failure(
        _CMD_BEGIN_ROUND,
        "Round Iteration has been removed from tech-plan; "
        "call advance-to-freeedit directly after init-complete.",
    )


def advance_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    return _failure(
        _CMD_ADVANCE_ROUND,
        "Round Iteration has been removed from tech-plan; "
        "call advance-to-freeedit directly after init-complete.",
    )


def advance_to_freeedit(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    if not progress_path.exists():
        return _failure(
            _CMD_ADVANCE_TO_FREEEDIT,
            "drafting-progress.md not found; run init-complete first",
        )

    data = load_drafting_progress(progress_path)
    step = data.get("current_step")
    if step == _STEP_FREE_EDIT:
        return _success(_CMD_ADVANCE_TO_FREEEDIT, current_step=_STEP_FREE_EDIT)

    if step not in (_STEP_READY, _STEP_ROUND):
        return _failure(
            _CMD_ADVANCE_TO_FREEEDIT,
            f"cannot advance to FreeEdit: current_step is {step!r} (expected Ready or RoundIteration)",
            current_step=step,
        )

    payload: dict[str, str] = {
        "version": "1",
        "cycle_id": data.get("cycle_id", cycle_id),
        "current_step": _STEP_FREE_EDIT,
    }
    if data.get("round"):
        payload["round"] = data["round"]
    save_drafting_progress(progress_path, payload, merge=False)
    return _success(_CMD_ADVANCE_TO_FREEEDIT, current_step=_STEP_FREE_EDIT)


def draft_status(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    if not progress_path.exists():
        return _failure(_CMD_STATUS, "drafting-progress.md not found")

    data = load_drafting_progress(progress_path)
    result: dict[str, Any] = {
        "current_step": data.get("current_step"),
        "cycle_id": data.get("cycle_id"),
    }
    if data.get("round"):
        result["round"] = int(data["round"])
    return _success(_CMD_STATUS, **result)


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _cli() -> int:
    parser = argparse.ArgumentParser(description="tech-plan draft control")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root directory",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(_CMD_BEGIN_INIT, help="Begin Initializing (gate + dispatch input)")
    sub.add_parser(_CMD_INIT_COMPLETE, help="Complete Initializing")
    sub.add_parser(_CMD_BEGIN_ROUND, help="[Deprecated] Was Round Iteration; now returns failure")
    sub.add_parser(_CMD_ADVANCE_ROUND, help="[Deprecated] Was round increment; now returns failure")
    sub.add_parser(_CMD_ADVANCE_TO_FREEEDIT, help="Transition Ready -> FreeEdit")
    sub.add_parser(_CMD_STATUS, help="Read drafting-progress snapshot")

    args = parser.parse_args()
    project_root = args.project_root.resolve()
    cycle_id = args.cycle_id.strip()

    try:
        if args.command == _CMD_BEGIN_INIT:
            result = begin_init(cycle_id, project_root)
            if result.get("ok"):
                print(result["dispatch_input"])
                return 0
            return _emit(result)
        if args.command == _CMD_INIT_COMPLETE:
            return _emit(init_complete(cycle_id, project_root))
        if args.command == _CMD_BEGIN_ROUND:
            return _emit(begin_round(cycle_id, project_root))
        if args.command == _CMD_ADVANCE_ROUND:
            return _emit(advance_round(cycle_id, project_root))
        if args.command == _CMD_ADVANCE_TO_FREEEDIT:
            return _emit(advance_to_freeedit(cycle_id, project_root))
        if args.command == _CMD_STATUS:
            return _emit(draft_status(cycle_id, project_root))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
