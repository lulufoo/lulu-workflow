#!/usr/bin/env python3
"""Draft control for tech-plan orchestrator.

Subcommands:
    init-probe     Check whether Initializing can start
    init-complete  Validate seeded tech-doc and write drafting-progress Ready
    begin-round    Transition Ready -> RoundIteration (round 1)
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
from workflow_common import read_md_field, session_state_path, tech_doc_path  # noqa: E402

_CMD_INIT_PROBE = "init-probe"
_CMD_INIT_COMPLETE = "init-complete"
_CMD_BEGIN_ROUND = "begin-round"
_STEP_READY = "Ready"
_STEP_ROUND = "RoundIteration"
_STATE_VECTOR_RE = re.compile(r"<!--\s*state-vector:")


def _active_doc(cycle_id: str, project_root: Path) -> int:
    ss_path = project_root / session_state_path(cycle_id)
    try:
        return int(read_md_field(ss_path, "active_doc", default="1"))
    except ValueError:
        return 1


def _tech_doc_path(cycle_id: str, project_root: Path) -> Path:
    return project_root / tech_doc_path(cycle_id, _active_doc(cycle_id, project_root))


def _success(command: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "command": command}
    payload.update(extra)
    return payload


def _failure(command: str, reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "command": command, "reason": reason}
    payload.update(extra)
    return payload


def _validate_tech_doc_seeded(tech_doc: Path) -> str | None:
    if not tech_doc.exists():
        return f"tech-doc.md not found: {tech_doc}"
    text = tech_doc.read_text(encoding="utf-8")
    if not _STATE_VECTOR_RE.search(text):
        return "tech-doc.md missing state-vector comment"
    return None


def init_probe(cycle_id: str, project_root: Path) -> dict[str, Any]:
    progress_path = resolve_drafting_progress_path_from_cycle(cycle_id, project_root)
    if not progress_path.exists():
        return _success(_CMD_INIT_PROBE, current_step=None)

    step = read_current_step(progress_path)
    if step == _STEP_READY:
        return _success(_CMD_INIT_PROBE, current_step=_STEP_READY)

    return _failure(
        _CMD_INIT_PROBE,
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

    sub.add_parser(_CMD_INIT_PROBE, help="Probe Initializing entry")
    sub.add_parser(_CMD_INIT_COMPLETE, help="Complete Initializing")
    sub.add_parser(_CMD_BEGIN_ROUND, help="Begin Round Iteration")

    args = parser.parse_args()
    project_root = args.project_root.resolve()
    cycle_id = args.cycle_id.strip()

    try:
        if args.command == _CMD_INIT_PROBE:
            return _emit(init_probe(cycle_id, project_root))
        if args.command == _CMD_INIT_COMPLETE:
            return _emit(init_complete(cycle_id, project_root))
        if args.command == _CMD_BEGIN_ROUND:
            return _emit(begin_round(cycle_id, project_root))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
