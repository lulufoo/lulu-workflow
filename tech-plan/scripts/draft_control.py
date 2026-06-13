#!/usr/bin/env python3
"""Draft control for tech-plan orchestrator.

Subcommands:
    begin-init            Check whether Initializing can start; on success print
                          initializing-runner ## Input block (plain text)
    init-complete         Validate seeded tech-doc and write drafting-progress Ready
    begin-round           Transition Ready -> RoundIteration (round 1)
    advance-round         Increment round while in RoundIteration
    advance-to-freeedit   Transition RoundIteration -> FreeEdit
    round-probe-input     Print prober-runner ## Input block (plain text); requires RoundIteration
    status                Read drafting-progress snapshot (read-only)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from drafting_progress_schema import (  # noqa: E402
    load_drafting_progress,
    read_current_step,
    resolve_drafting_progress_path_from_cycle,
    save_drafting_progress,
)
from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import (  # noqa: E402
    CACHE_DIR,
    decision_doc_path,
    detect_cycle_type,
    doc_dir,
    tech_doc_path,
)

_CMD_BEGIN_INIT = "begin-init"
_CMD_INIT_COMPLETE = "init-complete"
_CMD_BEGIN_ROUND = "begin-round"
_CMD_ADVANCE_ROUND = "advance-round"
_CMD_ADVANCE_TO_FREEEDIT = "advance-to-freeedit"
_CMD_ROUND_PROBE_INPUT = "round-probe-input"
_CMD_STATUS = "status"
_STEP_READY = "Ready"
_STEP_ROUND = "RoundIteration"
_STEP_FREE_EDIT = "FreeEdit"
_STATE_VECTOR_RE = re.compile(r"<!--\s*state-vector:")


def _tech_doc_path(cycle_id: str, project_root: Path) -> Path:
    return project_root / tech_doc_path(
        cycle_id,
        load_active_doc_from_cycle(cycle_id, project_root),
    )


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
    decision_doc: Path,
    cycle_type: str,
    cycle_id: str,
) -> str:
    return (
        f"REVISION_DIR:         {revision_dir.resolve().as_posix()}\n"
        f"DECISION_DOC_PATH:    {decision_doc.resolve().as_posix()}\n"
        f"CYCLE_TYPE:           {cycle_type}\n"
        f"CYCLE_ID:             {cycle_id}"
    )


def _init_dispatch_input(cycle_id: str, project_root: Path) -> str:
    active_doc = load_active_doc_from_cycle(cycle_id, project_root)
    revision_dir = project_root / doc_dir(cycle_id, active_doc)
    decision_doc = project_root / decision_doc_path(cycle_id)
    return _format_init_dispatch_input(
        revision_dir=revision_dir,
        decision_doc=decision_doc,
        cycle_type=detect_cycle_type(cycle_id),
        cycle_id=cycle_id,
    )


def _validate_tech_doc_seeded(tech_doc: Path) -> str | None:
    if not tech_doc.exists():
        return f"tech-doc.md not found: {tech_doc}"
    text = tech_doc.read_text(encoding="utf-8")
    if not _STATE_VECTOR_RE.search(text):
        return "tech-doc.md missing state-vector comment"
    return None


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
    tech_doc = _tech_doc_path(cycle_id, project_root)

    seed_error = _validate_tech_doc_seeded(tech_doc)
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
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    if not progress_path.exists():
        return _failure(
            _CMD_BEGIN_ROUND,
            "drafting-progress.md not found; run init-complete first",
        )

    step = read_current_step(progress_path)
    if step == _STEP_ROUND:
        data = load_drafting_progress(progress_path)
        return _success(
            _CMD_BEGIN_ROUND,
            current_step=_STEP_ROUND,
            round=int(data.get("round", "1")),
        )

    if step != _STEP_READY:
        return _failure(
            _CMD_BEGIN_ROUND,
            f"cannot begin round: current_step is {step!r} (expected Ready)",
            current_step=step,
        )

    save_drafting_progress(
        progress_path,
        {
            "version": "1",
            "cycle_id": cycle_id,
            "current_step": _STEP_ROUND,
            "round": "1",
        },
        merge=False,
    )
    return _success(_CMD_BEGIN_ROUND, current_step=_STEP_ROUND, round=1)


def advance_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    if not progress_path.exists():
        return _failure(
            _CMD_ADVANCE_ROUND,
            "drafting-progress.md not found; run begin-round first",
        )

    data = load_drafting_progress(progress_path)
    step = data.get("current_step")
    if step != _STEP_ROUND:
        return _failure(
            _CMD_ADVANCE_ROUND,
            f"cannot advance round: current_step is {step!r} (expected RoundIteration)",
            current_step=step,
        )

    current_round = max(1, int(data.get("round", "1")))
    new_round = current_round + 1
    save_drafting_progress(
        progress_path,
        {
            "version": "1",
            "cycle_id": data.get("cycle_id", cycle_id),
            "current_step": _STEP_ROUND,
            "round": str(new_round),
        },
        merge=False,
    )
    return _success(_CMD_ADVANCE_ROUND, current_step=_STEP_ROUND, round=new_round)


def advance_to_freeedit(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    if not progress_path.exists():
        return _failure(
            _CMD_ADVANCE_TO_FREEEDIT,
            "drafting-progress.md not found; run begin-round first",
        )

    data = load_drafting_progress(progress_path)
    step = data.get("current_step")
    if step == _STEP_FREE_EDIT:
        return _success(_CMD_ADVANCE_TO_FREEEDIT, current_step=_STEP_FREE_EDIT)

    if step != _STEP_ROUND:
        return _failure(
            _CMD_ADVANCE_TO_FREEEDIT,
            f"cannot advance to FreeEdit: current_step is {step!r} (expected RoundIteration)",
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


def _format_round_probe_input(
    *,
    cycle_dir: Path,
    cycle_id: str,
    cycle_type: str,
    round_n: int,
    tech_doc: Path,
) -> str:
    return (
        f"CYCLE_DIR:      {cycle_dir.resolve().as_posix()}\n"
        f"CYCLE_ID:       {cycle_id}\n"
        f"CYCLE_TYPE:     {cycle_type}\n"
        f"ROUND_N:        {round_n}\n"
        f"TECH_DOC_PATH:  {tech_doc.resolve().as_posix()}"
    )


def round_probe_input(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    if not progress_path.exists():
        return _failure(
            _CMD_ROUND_PROBE_INPUT,
            "drafting-progress.md not found; run begin-round first",
        )

    data = load_drafting_progress(progress_path)
    step = data.get("current_step")
    if step != _STEP_ROUND:
        return _failure(
            _CMD_ROUND_PROBE_INPUT,
            f"cannot generate probe input: current_step is {step!r} (expected RoundIteration)",
            current_step=step,
        )

    round_n = int(data.get("round", "1"))
    cycle_dir = project_root / CACHE_DIR / cycle_id
    tech_doc = project_root / tech_doc_path(
        cycle_id,
        load_active_doc_from_cycle(cycle_id, project_root),
    )
    dispatch_input = _format_round_probe_input(
        cycle_dir=cycle_dir,
        cycle_id=cycle_id,
        cycle_type=detect_cycle_type(cycle_id),
        round_n=round_n,
        tech_doc=tech_doc,
    )
    return _success(_CMD_ROUND_PROBE_INPUT, dispatch_input=dispatch_input)


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
    sub.add_parser(_CMD_BEGIN_ROUND, help="Begin Round Iteration")
    sub.add_parser(_CMD_ADVANCE_ROUND, help="Increment round counter")
    sub.add_parser(_CMD_ADVANCE_TO_FREEEDIT, help="Transition to FreeEdit")
    sub.add_parser(_CMD_ROUND_PROBE_INPUT, help="Print prober-runner Input block (requires RoundIteration)")
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
        if args.command == _CMD_ROUND_PROBE_INPUT:
            result = round_probe_input(cycle_id, project_root)
            if result.get("ok"):
                print(result["dispatch_input"])
                return 0
            return _emit(result)
        if args.command == _CMD_STATUS:
            return _emit(draft_status(cycle_id, project_root))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
