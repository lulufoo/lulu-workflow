#!/usr/bin/env python3
"""Eval control for tech-plan orchestrator.

Owns mechanical writes to evaluate-state.md. workflow-state transitions stay in
session_control.py.

Subcommands:
    init-round            Initialize evaluate-state.md (internal; session_control)
    begin-dimension       Mark dimension in_progress and return eval-runner inputs
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_state_schema import (  # noqa: E402
    init_evaluate_state,
    load_evaluate_state,
    resolve_evaluate_state_path_from_cycle,
    save_evaluate_state,
)
from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import (  # noqa: E402
    CACHE_DIR,
    detect_cycle_type,
    eval_round_dir,
    load_container_meta,
    tech_doc_path,
)
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
)

_CMD_INIT_ROUND = "init-round"
_CMD_BEGIN_DIMENSION = "begin-dimension"
_EXPECTED_EVALUATING_STATE = "Evaluating"
_VALID_EXECUTION_MODES = frozenset({"guided", "autonomous"})
_VALID_MODES = frozenset({"product", "tech"})
_VALID_DIMS = frozenset({"e1", "e2", "e3"})
_DISPATCH_BY_MODE = {"product": ["e1", "e2", "e3"], "tech": ["e2", "e3"]}
_SEVERITY_RANK = {"critical": 3, "medium": 2, "minor": 1}


def dispatch_list(mode: str) -> list[str]:
    """Return eval dimension dispatch sequence for workflow mode (SSOT)."""
    if mode not in _VALID_MODES:
        raise ValueError(
            f"invalid mode: {mode!r} (allowed: {sorted(_VALID_MODES)})"
        )
    return list(_DISPATCH_BY_MODE[mode])


def resolve_execution_mode(cycle_id: str, project_root: Path) -> str:
    """Return guided|autonomous from cycles.json (default guided)."""
    cycle_type = detect_cycle_type(cycle_id)
    cache_dir = project_root.resolve() / CACHE_DIR
    try:
        meta = load_container_meta(cache_dir, cycle_id, cycle_type)
    except ValueError:
        return "guided"
    if not meta:
        return "guided"
    mode = meta.get("execution_mode", "guided")
    if mode not in _VALID_EXECUTION_MODES:
        return "guided"
    return mode


def _success(command: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "command": command}
    payload.update(extra)
    return payload


def _failure(command: str, reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "command": command, "reason": reason}
    payload.update(extra)
    return payload


def _eval_paths(
    cycle_id: str,
    project_root: Path,
    *,
    active_doc: int,
    evaluate_round: int,
    es_path: Path,
) -> dict[str, str]:
    root = project_root.resolve()
    return {
        "tech_doc": (root / tech_doc_path(cycle_id, active_doc)).as_posix(),
        "evaluate_state": es_path.resolve().as_posix(),
        "evaluate_dir": (
            root / eval_round_dir(cycle_id, active_doc, evaluate_round)
        ).as_posix(),
    }


def build_eval_dispatch_payload(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Build eval-dispatch success/failure payload (no view field)."""
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current != _EXPECTED_EVALUATING_STATE:
        return _failure(
            "eval-dispatch",
            (
                f"current state is {current!r}, "
                f"expected {_EXPECTED_EVALUATING_STATE!r}."
            ),
            current_state=current,
        )

    try:
        evaluate_round = int(state.get("evaluate_round", "0"))
    except ValueError:
        evaluate_round = 0
    if evaluate_round < 1:
        return _failure(
            "eval-dispatch",
            f"evaluate_round is {evaluate_round!r} (expected >= 1).",
            current_state=current,
        )

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    if not es_path.exists():
        return _failure(
            "eval-dispatch",
            "evaluate-state.md not found.",
            current_state=current,
        )

    mode = state["mode"]
    active_doc = load_active_doc_from_cycle(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    return _success(
        "eval-dispatch",
        current_state=current,
        mode=mode,
        dispatch=dispatch_list(mode),
        evaluate_round=evaluate_round,
        M=evaluate_round,
        active_doc=active_doc,
        N=active_doc,
        cycle_type=detect_cycle_type(cycle_id),
        product_ref=state.get("product_ref", ""),
        project_root=project_root.resolve().as_posix(),
        paths=paths,
    )


def _format_runner_dispatch_input(runner_input: dict[str, str]) -> str:
    lines = [
        f"DIMENSION:            {runner_input['DIMENSION']}",
        f"CYCLE_TYPE:           {runner_input['CYCLE_TYPE']}",
        f"TECH_DOC_PATH:        {runner_input['TECH_DOC_PATH']}",
        f"EVALUATE_STATE_PATH:  {runner_input['EVALUATE_STATE_PATH']}",
        f"EVALUATE_DIR:         {runner_input['EVALUATE_DIR']}",
        f"EXECUTION_MODE:       {runner_input['EXECUTION_MODE']}",
    ]
    product_ref = runner_input.get("PRODUCT_REF", "")
    if product_ref:
        lines.append(f"PRODUCT_REF:          {product_ref}")
    lines.append(f"PROJECT_ROOT:         {runner_input['PROJECT_ROOT']}")
    return "\n".join(lines)


def _build_runner_input(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
    state: dict[str, str],
    paths: dict[str, str],
) -> dict[str, str]:
    runner_input = {
        "DIMENSION": dim,
        "CYCLE_TYPE": detect_cycle_type(cycle_id),
        "TECH_DOC_PATH": paths["tech_doc"],
        "EVALUATE_STATE_PATH": paths["evaluate_state"],
        "EVALUATE_DIR": paths["evaluate_dir"],
        "EXECUTION_MODE": resolve_execution_mode(cycle_id, project_root),
        "PROJECT_ROOT": project_root.resolve().as_posix(),
    }
    if dim == "e1":
        runner_input["PRODUCT_REF"] = state.get("product_ref", "")
    return runner_input


def init_round(
    cycle_id: str,
    project_root: Path,
    *,
    mode: str,
) -> dict[str, Any]:
    """Initialize evaluate-state.md for the current active revision.

    Caller must ensure workflow-state is already Evaluating. Does not read or
    write workflow-state.md. Not idempotent — session_control skips re-entry.
    """
    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    init_evaluate_state(es_path, mode=mode)
    return _success(
        _CMD_INIT_ROUND,
        mode=mode,
        path=es_path.resolve().as_posix(),
    )


def begin_dimension(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Mark dimension in_progress and return eval-runner input block."""
    if dim not in _VALID_DIMS:
        return _failure(
            _CMD_BEGIN_DIMENSION,
            f"invalid dim: {dim!r} (allowed: {sorted(_VALID_DIMS)})",
        )

    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    current = state["current_state"]
    if current != _EXPECTED_EVALUATING_STATE:
        return _failure(
            _CMD_BEGIN_DIMENSION,
            (
                f"current state is {current!r}, "
                f"expected {_EXPECTED_EVALUATING_STATE!r}."
            ),
            current_state=current,
        )

    mode = state["mode"]
    if dim not in dispatch_list(mode):
        return _failure(
            _CMD_BEGIN_DIMENSION,
            f"dim {dim!r} is not in dispatch list for mode {mode!r}.",
            current_state=current,
        )

    try:
        evaluate_round = int(state.get("evaluate_round", "0"))
    except ValueError:
        evaluate_round = 0
    if evaluate_round < 1:
        return _failure(
            _CMD_BEGIN_DIMENSION,
            f"evaluate_round is {evaluate_round!r} (expected >= 1).",
            current_state=current,
        )

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    if not es_path.exists():
        return _failure(
            _CMD_BEGIN_DIMENSION,
            "evaluate-state.md not found.",
            current_state=current,
        )

    active_doc = load_active_doc_from_cycle(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )

    eval_data = load_evaluate_state(es_path)
    eval_data["current_dimension"] = dim
    eval_data[f"{dim}_status"] = "in_progress"
    save_evaluate_state(es_path, eval_data)

    runner_input = _build_runner_input(
        cycle_id,
        project_root,
        dim=dim,
        state=state,
        paths=paths,
    )
    return _success(
        _CMD_BEGIN_DIMENSION,
        dim=dim,
        current_state=current,
        runner_input=runner_input,
        dispatch_input=_format_runner_dispatch_input(runner_input),
    )


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def _cli() -> int:
    parser = argparse.ArgumentParser(description="tech-plan eval control")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root directory",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    begin_parser = sub.add_parser(
        _CMD_BEGIN_DIMENSION,
        help="Begin a single eval dimension",
    )
    begin_parser.add_argument(
        "--dim",
        required=True,
        choices=sorted(_VALID_DIMS),
        help="Dimension: e1, e2, or e3",
    )

    args = parser.parse_args()
    project_root = args.project_root.resolve()
    cycle_id = args.cycle_id.strip()

    try:
        if args.command == _CMD_BEGIN_DIMENSION:
            payload = begin_dimension(cycle_id, project_root, dim=args.dim)
            if payload.get("ok") and "dispatch_input" in payload:
                print(payload["dispatch_input"])
                return 0
            return _emit(payload)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(_cli())
