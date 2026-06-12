#!/usr/bin/env python3
"""Eval control for tech-plan orchestrator.

Owns mechanical writes to evaluate-state.md. workflow-state transitions stay in
session_control.py, except resume-drafting (eval fix exit after complete-round).

Subcommands:
    init-round                  Initialize evaluate-state.md (internal; session_control)
    begin-eval-round            Enter Evaluating or start next round; return loop payload
    begin-dimension             Mark dimension in_progress and return eval-runner inputs
    finish-dimension-probe      Validate review and mark dimension probed (locked)
    check-dimension             Read-only verify dimension probed after eval-runner
    probe-complete              Sum issues; advance fix_phase to artifact-remediation
    begin-artifact-remediation  Return artifact remediation dispatch input or skip
    check-artifact-remediation  Reconcile WO-* rows; advance fix_phase
    begin-sot-remediation       Return SoT remediation dispatch input or skip
    check-sot-remediation       Reconcile SOT-* rows; set fix_phase done / abandoned
    complete-round              Finalize evaluate-state and return summary payload
    resume-drafting             Evaluating -> Drafting after complete-round (fix exit)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_EVAL_LIB = Path(__file__).resolve().parents[2] / "eval" / "scripts"
sys.path.insert(0, str(_EVAL_LIB))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from review_io import (  # noqa: E402
    count_resolved,
    has_escalated,
    has_pending_sot,
    parse_review_file,
    pending_artifact_rows,
    pending_sot_rows,
)
from review_schema import validate_review_file  # noqa: E402
from evaluate_state_schema import (  # noqa: E402
    all_dims_at_least,
    build_initial_evaluate_state,
    dispatch_dims,
    init_evaluate_state,
    is_v2_state,
    load_evaluate_state,
    merge_current_dimension,
    parse_current_dimension,
    resolve_evaluate_state_path_from_cycle,
    save_evaluate_state,
    save_evaluate_state_locked,
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
    save_workflow_state,
)

_CMD_INIT_ROUND = "init-round"
_CMD_BEGIN_EVAL_ROUND = "begin-eval-round"
_CMD_BEGIN_DIMENSION = "begin-dimension"
_CMD_FINISH_DIMENSION_PROBE = "finish-dimension-probe"
_CMD_CHECK_DIMENSION = "check-dimension"
_CMD_PROBE_COMPLETE = "probe-complete"
_CMD_BEGIN_ARTIFACT_REMEDIATION = "begin-artifact-remediation"
_CMD_CHECK_ARTIFACT_REMEDIATION = "check-artifact-remediation"
_CMD_BEGIN_SOT_REMEDIATION = "begin-sot-remediation"
_CMD_CHECK_SOT_REMEDIATION = "check-sot-remediation"
_CMD_COMPLETE_ROUND = "complete-round"
_CMD_RESUME_DRAFTING = "resume-drafting"

_DIM_TO_REVIEW_INDEX = {"e1": "1", "e2": "2", "e3": "3"}
_REVIEW_FILE_RE = re.compile(r"tech-review-e\d+([123])\.md$")
_DIM_INDEX_TO_NAME = {"1": "e1", "2": "e2", "3": "e3"}
_ENTRY_V2_KEYS = ("version", "eval_status", "fix_phase", "current_dimension")
_EXPECTED_EVALUATING_STATE = "Evaluating"
_VALID_EXECUTION_MODES = frozenset({"guided", "autonomous"})
_VALID_MODES = frozenset({"product", "tech"})
_VALID_DIMS = frozenset({"e1", "e2", "e3"})
_SEVERITY_RANK = {"critical": 3, "medium": 2, "minor": 1}


def dispatch_list(mode: str) -> list[str]:
    """Return eval dimension dispatch sequence for workflow mode (SSOT)."""
    return dispatch_dims(mode)


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


def _validate_evaluate_state_for_mode(
    eval_data: dict[str, str],
    mode: str,
) -> str | None:
    """Return error reason when evaluate-state does not match mode at entry."""
    if not is_v2_state(eval_data):
        return (
            "evaluate-state version 1 is not supported; "
            "start a new eval round (Re-evaluate)."
        )
    if eval_data.get("phase") != "evaluate":
        return f"phase is {eval_data.get('phase')!r}, expected 'evaluate'."
    try:
        expected = build_initial_evaluate_state(mode=mode)
    except ValueError as exc:
        return str(exc)
    for key in _ENTRY_V2_KEYS:
        actual = eval_data.get(key)
        exp = expected.get(key)
        if actual != exp:
            return (
                f"{key} is {actual!r}, expected {exp!r} "
                f"for mode {mode!r}."
            )
    return None


def _review_path_for_dim(
    eval_dir: Path,
    evaluate_round: int,
    dim: str,
) -> Path:
    index = _DIM_TO_REVIEW_INDEX[dim]
    return eval_dir / f"tech-review-e{evaluate_round}{index}.md"


def dimension_from_review_path(path: Path) -> str:
    match = _REVIEW_FILE_RE.search(path.name)
    if not match:
        return ""
    return _DIM_INDEX_TO_NAME.get(match.group(1), "")


def collect_review_issues(
    eval_dir: Path,
) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[dict[str, str]] = []
    review_paths: list[str] = []
    if not eval_dir.is_dir():
        return issues, review_paths

    for path in sorted(eval_dir.glob("tech-review-e*.md")):
        dimension = dimension_from_review_path(path)
        if not dimension:
            continue
        review_paths.append(path.as_posix())
        for row in parse_review_file(path):
            issues.append({**row, "dimension": dimension})
    return issues, review_paths


def build_dimensions(eval_state: dict[str, str]) -> list[dict[str, str]]:
    dim_map = parse_current_dimension(eval_state.get("current_dimension", "{}"))
    dimensions: list[dict[str, str]] = []
    for dim, status in dim_map.items():
        if status == "pending":
            continue
        dimensions.append({
            "dim": dim,
            "status": status,
            "total": eval_state.get(f"{dim}_total_issues", "0"),
            "resolved": eval_state.get(f"{dim}_resolved_issues", "0"),
        })
    return dimensions


def count_ignored(issues: list[dict[str, str]]) -> int:
    return sum(
        1 for issue in issues if issue.get("decision", "").lower() == "ignore"
    )


def _reason_from_issue(issue: dict[str, str]) -> str:
    issue_id = issue.get("id", "")
    description = issue.get("description", "")
    if issue_id and description:
        return f"{issue_id}: {description}"
    return description or issue_id


def compute_fix_severity(
    issues: list[dict[str, str]],
) -> tuple[str, str]:
    """Return fix_severity and fix_severity_reason from parsed review issues."""
    if not issues:
        return "minor", ""

    ranked = sorted(
        issues,
        key=lambda issue: _SEVERITY_RANK.get(
            issue.get("severity", "").lower(),
            0,
        ),
        reverse=True,
    )
    top = ranked[0]
    severity = top.get("severity", "minor").lower()
    if severity not in _SEVERITY_RANK:
        severity = "minor"
    if all(issue.get("decision", "").lower() == "ignore" for issue in issues):
        severity = "minor"
    return severity, _reason_from_issue(top)


def build_issue_counts(
    eval_state: dict[str, str],
    issues: list[dict[str, str]],
) -> dict[str, int]:
    total_issues = int(eval_state.get("total_issues", "0") or "0")
    resolved_issues = int(eval_state.get("resolved_issues", "0") or "0")
    ignored_issues = count_ignored(issues)
    if ignored_issues == 0 and total_issues > resolved_issues:
        ignored_issues = total_issues - resolved_issues
    return {
        "total_issues": total_issues,
        "resolved_issues": resolved_issues,
        "ignored_issues": ignored_issues,
    }


def _load_evaluating_context(
    cycle_id: str,
    project_root: Path,
) -> tuple[dict[str, str], Path, dict[str, str], int, int, str] | dict[str, Any]:
    """Return (state, ws_path, eval_data, evaluate_round, active_doc, mode) or failure."""
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    current = state["current_state"]
    if current != _EXPECTED_EVALUATING_STATE:
        return _failure(
            "",
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
            "",
            f"evaluate_round is {evaluate_round!r} (expected >= 1).",
            current_state=current,
        )

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    if not es_path.exists():
        return _failure(
            "",
            "evaluate-state.md not found.",
            current_state=current,
        )

    try:
        eval_data = load_evaluate_state(es_path)
    except ValueError as exc:
        return _failure("", str(exc), current_state=current)

    if not is_v2_state(eval_data):
        return _failure(
            "",
            "evaluate-state version 1 is not supported; start a new eval round.",
            current_state=current,
        )

    active_doc = load_active_doc_from_cycle(cycle_id, project_root)
    mode = state["mode"]
    return state, ws_path, eval_data, evaluate_round, active_doc, mode


def build_eval_loop_payload(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Build eval loop context payload (requires Evaluating + evaluate-state)."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_BEGIN_EVAL_ROUND
        return ctx

    state, _ws_path, _eval_data, evaluate_round, active_doc, mode = ctx
    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    return _success(
        _CMD_BEGIN_EVAL_ROUND,
        current_state=state["current_state"],
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


def _start_next_eval_round(
    cycle_id: str,
    project_root: Path,
    *,
    state: dict[str, str],
    ws_path: Path,
    mode: str,
) -> dict[str, Any]:
    """Increment evaluate_round, re-init evaluate-state, return loop payload."""
    try:
        evaluate_round = int(state.get("evaluate_round", "0")) + 1
    except ValueError:
        evaluate_round = 1

    merged = dict(state)
    merged["evaluate_round"] = str(evaluate_round)
    save_workflow_state(ws_path, merged, merge=False)
    init_round(cycle_id, project_root, mode=mode)
    return build_eval_loop_payload(cycle_id, project_root)


def begin_eval_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Enter Evaluating or start next eval round; validate evaluate-state; return payload."""
    from session_control import start_evaluating  # noqa: WPS433

    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    current = state["current_state"]
    mode = state["mode"]
    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)

    if current == _EXPECTED_EVALUATING_STATE:
        if not es_path.exists():
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                "evaluate-state.md not found.",
                current_state=current,
            )

        try:
            eval_data = load_evaluate_state(es_path)
        except ValueError as exc:
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                str(exc),
                current_state=current,
            )

        if not is_v2_state(eval_data):
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                "evaluate-state version 1 is not supported; start a new eval round.",
                current_state=current,
            )

        eval_status = eval_data.get("eval_status", "")
        if eval_status == "done":
            return _start_next_eval_round(
                cycle_id,
                project_root,
                state=state,
                ws_path=ws_path,
                mode=mode,
            )
        if eval_status == "abandoned":
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                "evaluation was abandoned (eval_status: abandoned).",
                current_state=current,
            )

        mismatch = _validate_evaluate_state_for_mode(eval_data, mode)
        if mismatch:
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                mismatch,
                current_state=current,
            )
        return build_eval_loop_payload(cycle_id, project_root)

    entry = start_evaluating(cycle_id, project_root)
    if not entry.get("ok"):
        resume = entry.get("resume", {})
        return _failure(
            _CMD_BEGIN_EVAL_ROUND,
            resume.get("action")
            or (
                f"cannot enter Evaluating from state "
                f"{entry.get('current_state', '')!r}."
            ),
            current_state=entry.get("current_state", ""),
        )

    state = load_workflow_state(ws_path)
    mode = state["mode"]

    try:
        eval_data = load_evaluate_state(es_path)
    except ValueError as exc:
        return _failure(
            _CMD_BEGIN_EVAL_ROUND,
            str(exc),
            current_state=state["current_state"],
        )

    mismatch = _validate_evaluate_state_for_mode(eval_data, mode)
    if mismatch:
        return _failure(
            _CMD_BEGIN_EVAL_ROUND,
            mismatch,
            current_state=state["current_state"],
        )

    return build_eval_loop_payload(cycle_id, project_root)


def _format_runner_dispatch_input(runner_input: dict[str, str]) -> str:
    lines = [
        f"DIMENSION:            {runner_input['DIMENSION']}",
        f"CYCLE_ID:             {runner_input['CYCLE_ID']}",
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
        "CYCLE_ID": cycle_id,
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
    """Initialize evaluate-state.md for the current active revision."""
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

    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_BEGIN_DIMENSION
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if dim not in dispatch_list(mode):
        return _failure(
            _CMD_BEGIN_DIMENSION,
            f"dim {dim!r} is not in dispatch list for mode {mode!r}.",
            current_state=state["current_state"],
        )

    if eval_data.get("fix_phase") != "probe":
        return _failure(
            _CMD_BEGIN_DIMENSION,
            f"fix_phase is {eval_data.get('fix_phase')!r}, expected 'probe'.",
            current_state=state["current_state"],
        )

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )

    def _patch(data: dict[str, str]) -> dict[str, str]:
        updated = merge_current_dimension(data, dim, "in_progress")
        return updated

    save_evaluate_state_locked(es_path, _patch)

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
        current_state=state["current_state"],
        runner_input=runner_input,
        dispatch_input=_format_runner_dispatch_input(runner_input),
    )


def finish_dimension_probe(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Validate review file and mark dimension probed (locked write)."""
    if dim not in _VALID_DIMS:
        return _failure(
            _CMD_FINISH_DIMENSION_PROBE,
            f"invalid dim: {dim!r} (allowed: {sorted(_VALID_DIMS)})",
            dim=dim,
        )

    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_FINISH_DIMENSION_PROBE
        ctx["dim"] = dim
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if dim not in dispatch_list(mode):
        return _failure(
            _CMD_FINISH_DIMENSION_PROBE,
            f"dim {dim!r} is not in dispatch list for mode {mode!r}.",
            dim=dim,
        )

    eval_dir = project_root.resolve() / eval_round_dir(
        cycle_id,
        active_doc,
        evaluate_round,
    )
    review_path = _review_path_for_dim(eval_dir, evaluate_round, dim)
    validation_errors = validate_review_file(review_path, phase="probe")
    if validation_errors:
        return _failure(
            _CMD_FINISH_DIMENSION_PROBE,
            "; ".join(validation_errors),
            dim=dim,
            review_path=review_path.as_posix(),
        )

    rows = parse_review_file(review_path)
    total_issues = str(len(rows))

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)

    def _patch(data: dict[str, str]) -> dict[str, str]:
        updated = merge_current_dimension(data, dim, "probed")
        updated[f"{dim}_total_issues"] = total_issues
        return updated

    save_evaluate_state_locked(es_path, _patch)

    return _success(
        _CMD_FINISH_DIMENSION_PROBE,
        dim=dim,
        outcome="probed",
        total_issues=total_issues,
        review_path=review_path.resolve().as_posix(),
    )


def check_dimension(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Read-only verify dimension probed after eval-runner."""
    if dim not in _VALID_DIMS:
        return _failure(
            _CMD_CHECK_DIMENSION,
            f"invalid dim: {dim!r} (allowed: {sorted(_VALID_DIMS)})",
            dim=dim,
            outcome="incomplete",
            abandoned=False,
        )

    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_CHECK_DIMENSION
        ctx["dim"] = dim
        ctx["outcome"] = "incomplete"
        ctx["abandoned"] = False
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if dim not in dispatch_list(mode):
        return _failure(
            _CMD_CHECK_DIMENSION,
            f"dim {dim!r} is not in dispatch list for mode {mode!r}.",
            current_state=state["current_state"],
            dim=dim,
            outcome="incomplete",
            abandoned=False,
        )

    eval_status = eval_data.get("eval_status", "")
    if eval_status == "abandoned":
        return _success(
            _CMD_CHECK_DIMENSION,
            dim=dim,
            outcome="abandoned",
            abandoned=True,
            current_state=state["current_state"],
            eval_status=eval_status,
        )

    dim_map = parse_current_dimension(eval_data.get("current_dimension", "{}"))
    dim_status = dim_map.get(dim, "pending")

    eval_dir = project_root.resolve() / eval_round_dir(
        cycle_id,
        active_doc,
        evaluate_round,
    )
    review_path = _review_path_for_dim(eval_dir, evaluate_round, dim)

    if review_path.exists() and dim_status != "probed":
        return _failure(
            _CMD_CHECK_DIMENSION,
            (
                f"review exists but {dim} status is {dim_status!r}, "
                "expected 'probed' (runner forgot finish-dimension-probe?)."
            ),
            current_state=state["current_state"],
            dim=dim,
            outcome="incomplete",
            abandoned=False,
            dim_status=dim_status,
            review_path=review_path.resolve().as_posix(),
        )

    if dim_status != "probed":
        return _failure(
            _CMD_CHECK_DIMENSION,
            f"{dim} status is {dim_status!r}, expected 'probed'.",
            current_state=state["current_state"],
            dim=dim,
            outcome="incomplete",
            abandoned=False,
            dim_status=dim_status,
        )

    validation_errors = validate_review_file(review_path, phase="probe")
    if validation_errors:
        return _failure(
            _CMD_CHECK_DIMENSION,
            "; ".join(validation_errors),
            current_state=state["current_state"],
            dim=dim,
            outcome="incomplete",
            abandoned=False,
            review_path=review_path.resolve().as_posix(),
        )

    rows = parse_review_file(review_path)
    for row in rows:
        row["dimension"] = dim

    return _success(
        _CMD_CHECK_DIMENSION,
        dim=dim,
        outcome="probed",
        abandoned=False,
        current_state=state["current_state"],
        eval_status=eval_status,
        dim_status=dim_status,
        total_issues=eval_data.get(f"{dim}_total_issues", "0"),
        review_path=review_path.resolve().as_posix(),
        issues=rows,
    )


def probe_complete(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Sum total_issues and advance fix_phase to artifact-remediation."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_PROBE_COMPLETE
        return ctx

    state, _ws_path, eval_data, _evaluate_round, _active_doc, mode = ctx
    dispatch = dispatch_list(mode)

    if eval_data.get("fix_phase") != "probe":
        return _failure(
            _CMD_PROBE_COMPLETE,
            f"fix_phase is {eval_data.get('fix_phase')!r}, expected 'probe'.",
            current_state=state["current_state"],
        )

    if not all_dims_at_least(eval_data, dispatch, "probed"):
        return _failure(
            _CMD_PROBE_COMPLETE,
            "not all dispatch dimensions are probed.",
            current_state=state["current_state"],
        )

    total = sum(
        int(eval_data.get(f"{dim}_total_issues", "0") or "0")
        for dim in dispatch
    )

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    save_evaluate_state(
        es_path,
        {
            "total_issues": str(total),
            "fix_phase": "artifact-remediation",
        },
    )

    return _success(
        _CMD_PROBE_COMPLETE,
        fix_phase="artifact-remediation",
        total_issues=str(total),
        current_state=state["current_state"],
    )


def _remediation_dispatch_input(
    cycle_id: str,
    project_root: Path,
    *,
    state: dict[str, str],
    paths: dict[str, str],
    evaluate_round: int,
) -> dict[str, str]:
    return {
        "CYCLE_ID": cycle_id,
        "CYCLE_TYPE": detect_cycle_type(cycle_id),
        "TECH_DOC_PATH": paths["tech_doc"],
        "EVALUATE_DIR": paths["evaluate_dir"],
        "EVALUATE_STATE_PATH": paths["evaluate_state"],
        "EXECUTION_MODE": resolve_execution_mode(cycle_id, project_root),
        "PROJECT_ROOT": project_root.resolve().as_posix(),
        "EVALUATE_ROUND": str(evaluate_round),
        "PRODUCT_REF": state.get("product_ref", ""),
    }


def _format_remediation_dispatch_input(data: dict[str, str]) -> str:
    lines = [
        f"CYCLE_ID:             {data['CYCLE_ID']}",
        f"CYCLE_TYPE:           {data['CYCLE_TYPE']}",
        f"TECH_DOC_PATH:        {data['TECH_DOC_PATH']}",
        f"EVALUATE_DIR:         {data['EVALUATE_DIR']}",
        f"EVALUATE_STATE_PATH:  {data['EVALUATE_STATE_PATH']}",
        f"EXECUTION_MODE:       {data['EXECUTION_MODE']}",
        f"EVALUATE_ROUND:       {data['EVALUATE_ROUND']}",
        f"PROJECT_ROOT:         {data['PROJECT_ROOT']}",
    ]
    if data.get("PRODUCT_REF"):
        lines.append(f"PRODUCT_REF:          {data['PRODUCT_REF']}")
    return "\n".join(lines)


def begin_artifact_remediation(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Return artifact remediation dispatch input or skip when no pending WO-* rows."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_BEGIN_ARTIFACT_REMEDIATION
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if eval_data.get("fix_phase") != "artifact-remediation":
        return _failure(
            _CMD_BEGIN_ARTIFACT_REMEDIATION,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'artifact-remediation'."
            ),
            current_state=state["current_state"],
        )

    eval_dir = project_root.resolve() / eval_round_dir(
        cycle_id,
        active_doc,
        evaluate_round,
    )
    all_rows: list[dict[str, str]] = []
    for dim in dispatch_list(mode):
        review_path = _review_path_for_dim(eval_dir, evaluate_round, dim)
        for row in parse_review_file(review_path):
            all_rows.append({**row, "dimension": dim})

    pending = pending_artifact_rows(all_rows)
    if not pending:
        return _success(
            _CMD_BEGIN_ARTIFACT_REMEDIATION,
            skip=True,
            current_state=state["current_state"],
        )

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    dispatch_data = _remediation_dispatch_input(
        cycle_id,
        project_root,
        state=state,
        paths=paths,
        evaluate_round=evaluate_round,
    )
    return _success(
        _CMD_BEGIN_ARTIFACT_REMEDIATION,
        skip=False,
        current_state=state["current_state"],
        pending_count=len(pending),
        dispatch_input=_format_remediation_dispatch_input(dispatch_data),
        runner_input=dispatch_data,
    )


def check_artifact_remediation(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Reconcile WO-* rows and advance fix_phase to sot-remediation."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_CHECK_ARTIFACT_REMEDIATION
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    dispatch = dispatch_list(mode)
    eval_dir = project_root.resolve() / eval_round_dir(
        cycle_id,
        active_doc,
        evaluate_round,
    )

    patch: dict[str, str] = {}
    dim_resolved: dict[str, int] = {}
    for dim in dispatch:
        review_path = _review_path_for_dim(eval_dir, evaluate_round, dim)
        errors = validate_review_file(review_path, phase="probe")
        if errors:
            return _failure(
                _CMD_CHECK_ARTIFACT_REMEDIATION,
                f"{dim}: {'; '.join(errors)}",
                current_state=state["current_state"],
            )
        rows = parse_review_file(review_path)
        dim_resolved[dim] = count_resolved(rows)
        patch[f"{dim}_resolved_issues"] = str(dim_resolved[dim])
        if not has_pending_sot(rows):
            eval_data = merge_current_dimension(eval_data, dim, "complete")
            patch["current_dimension"] = eval_data["current_dimension"]

    resolved_total = sum(dim_resolved.values())
    patch["resolved_issues"] = str(resolved_total)
    patch["fix_phase"] = "sot-remediation"

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    save_evaluate_state(es_path, patch)

    return _success(
        _CMD_CHECK_ARTIFACT_REMEDIATION,
        fix_phase="sot-remediation",
        current_state=state["current_state"],
        dim_resolved=dim_resolved,
        resolved_issues=str(resolved_total),
    )


def begin_sot_remediation(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Return SoT remediation dispatch input or skip when no pending SOT-* rows."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_BEGIN_SOT_REMEDIATION
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if eval_data.get("fix_phase") != "sot-remediation":
        return _failure(
            _CMD_BEGIN_SOT_REMEDIATION,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'sot-remediation'."
            ),
            current_state=state["current_state"],
        )

    eval_dir = project_root.resolve() / eval_round_dir(
        cycle_id,
        active_doc,
        evaluate_round,
    )
    all_rows: list[dict[str, str]] = []
    for dim in dispatch_list(mode):
        review_path = _review_path_for_dim(eval_dir, evaluate_round, dim)
        for row in parse_review_file(review_path):
            all_rows.append({**row, "dimension": dim})

    pending = pending_sot_rows(all_rows)
    if not pending:
        return _success(
            _CMD_BEGIN_SOT_REMEDIATION,
            skip=True,
            current_state=state["current_state"],
        )

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    dispatch_data = _remediation_dispatch_input(
        cycle_id,
        project_root,
        state=state,
        paths=paths,
        evaluate_round=evaluate_round,
    )
    return _success(
        _CMD_BEGIN_SOT_REMEDIATION,
        skip=False,
        current_state=state["current_state"],
        pending_count=len(pending),
        dispatch_input=_format_remediation_dispatch_input(dispatch_data),
        runner_input=dispatch_data,
    )


def check_sot_remediation(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Reconcile SOT-* rows; set fix_phase done; abandoned if escalated."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_CHECK_SOT_REMEDIATION
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    dispatch = dispatch_list(mode)
    eval_dir = project_root.resolve() / eval_round_dir(
        cycle_id,
        active_doc,
        evaluate_round,
    )

    escalated = False
    patch: dict[str, str] = {}
    dim_resolved: dict[str, int] = {}
    for dim in dispatch:
        review_path = _review_path_for_dim(eval_dir, evaluate_round, dim)
        errors = validate_review_file(review_path, phase="remediation")
        if errors:
            return _failure(
                _CMD_CHECK_SOT_REMEDIATION,
                f"{dim}: {'; '.join(errors)}",
                current_state=state["current_state"],
            )
        rows = parse_review_file(review_path)
        dim_resolved[dim] = count_resolved(rows)
        patch[f"{dim}_resolved_issues"] = str(dim_resolved[dim])
        if has_escalated(rows):
            escalated = True
        dim_map = parse_current_dimension(eval_data.get("current_dimension", "{}"))
        if dim_map.get(dim) == "probed":
            eval_data = merge_current_dimension(eval_data, dim, "complete")
            patch["current_dimension"] = eval_data["current_dimension"]

    resolved_total = sum(dim_resolved.values())
    patch["resolved_issues"] = str(resolved_total)
    patch["fix_phase"] = "done"
    if escalated:
        patch["eval_status"] = "abandoned"

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    save_evaluate_state(es_path, patch)
    eval_data_after = load_evaluate_state(es_path)
    if not all_dims_at_least(eval_data_after, dispatch, "complete"):
        dim_map = parse_current_dimension(
            eval_data_after.get("current_dimension", "{}"),
        )
        incomplete = [
            dim for dim in dispatch if dim_map.get(dim) != "complete"
        ]
        return _failure(
            _CMD_CHECK_SOT_REMEDIATION,
            (
                f"dispatch dimensions not complete after SoT remediation: "
                f"{incomplete!r}."
            ),
            current_state=state["current_state"],
            incomplete_dims=incomplete,
        )

    return _success(
        _CMD_CHECK_SOT_REMEDIATION,
        fix_phase="done",
        abandoned=escalated,
        current_state=state["current_state"],
        dim_resolved=dim_resolved,
        resolved_issues=str(resolved_total),
    )


def complete_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Finalize evaluation round: compute severity, write done, return summary."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_COMPLETE_ROUND
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    dispatch = dispatch_list(mode)

    eval_status = eval_data.get("eval_status", "")
    if eval_status == "done":
        return _failure(
            _CMD_COMPLETE_ROUND,
            "evaluate round is already complete (eval_status: done).",
            current_state=state["current_state"],
        )
    if eval_status == "abandoned":
        return _failure(
            _CMD_COMPLETE_ROUND,
            "evaluation was abandoned (eval_status: abandoned).",
            current_state=state["current_state"],
        )
    if eval_data.get("fix_phase") != "done":
        return _failure(
            _CMD_COMPLETE_ROUND,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'done'."
            ),
            current_state=state["current_state"],
        )

    if not all_dims_at_least(eval_data, dispatch, "complete"):
        return _failure(
            _CMD_COMPLETE_ROUND,
            "not all dispatch dimensions are complete.",
            current_state=state["current_state"],
        )

    eval_dir = project_root.resolve() / eval_round_dir(
        cycle_id,
        active_doc,
        evaluate_round,
    )
    issues, review_paths = collect_review_issues(eval_dir)
    fix_severity, fix_severity_reason = compute_fix_severity(issues)

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    save_evaluate_state(
        es_path,
        {
            "eval_status": "done",
            "fix_severity": fix_severity,
            "fix_severity_reason": fix_severity_reason,
        },
    )
    eval_data = load_evaluate_state(es_path)

    return _success(
        _CMD_COMPLETE_ROUND,
        evaluate_round=evaluate_round,
        current_state=state["current_state"],
        eval_status="done",
        fix_severity=eval_data.get("fix_severity", ""),
        fix_severity_reason=eval_data.get("fix_severity_reason", ""),
        counts=build_issue_counts(eval_data, issues),
        dimensions=build_dimensions(eval_data),
        issues=issues,
        review_paths=review_paths,
    )


def resume_drafting(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Return to Drafting after complete-round (Evaluating fix exit)."""
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    current = state["current_state"]
    if current != _EXPECTED_EVALUATING_STATE:
        return _failure(
            _CMD_RESUME_DRAFTING,
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
            _CMD_RESUME_DRAFTING,
            f"evaluate_round is {evaluate_round!r} (expected >= 1).",
            current_state=current,
        )

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    if not es_path.exists():
        return _failure(
            _CMD_RESUME_DRAFTING,
            "evaluate-state.md not found.",
            current_state=current,
        )

    eval_data = load_evaluate_state(es_path)
    eval_status = eval_data.get("eval_status", "")
    if eval_status == "abandoned":
        return _failure(
            _CMD_RESUME_DRAFTING,
            "evaluation was abandoned (eval_status: abandoned).",
            current_state=current,
        )
    if eval_status != "done":
        return _failure(
            _CMD_RESUME_DRAFTING,
            (
                f"eval_status is {eval_status!r}, "
                "expected 'done' (run complete-round first)."
            ),
            current_state=current,
        )

    merged = dict(state)
    merged["current_state"] = "Drafting"
    merged.pop("skip_evaluate_requested", None)
    save_workflow_state(ws_path, merged, merge=False)

    return _success(
        _CMD_RESUME_DRAFTING,
        current_state="Drafting",
        evaluate_round=evaluate_round,
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

    sub.add_parser(
        _CMD_BEGIN_EVAL_ROUND,
        help="Enter Evaluating and return eval loop payload",
    )

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

    finish_parser = sub.add_parser(
        _CMD_FINISH_DIMENSION_PROBE,
        help="Validate review and mark dimension probed",
    )
    finish_parser.add_argument(
        "--dim",
        required=True,
        choices=sorted(_VALID_DIMS),
        help="Dimension: e1, e2, or e3",
    )

    check_parser = sub.add_parser(
        _CMD_CHECK_DIMENSION,
        help="Read single-dimension outcome after eval-runner",
    )
    check_parser.add_argument(
        "--dim",
        required=True,
        choices=sorted(_VALID_DIMS),
        help="Dimension: e1, e2, or e3",
    )

    sub.add_parser(
        _CMD_PROBE_COMPLETE,
        help="Sum probe issues and advance to artifact remediation",
    )
    sub.add_parser(
        _CMD_BEGIN_ARTIFACT_REMEDIATION,
        help="Begin artifact remediation or skip",
    )
    sub.add_parser(
        _CMD_CHECK_ARTIFACT_REMEDIATION,
        help="Check artifact remediation complete",
    )
    sub.add_parser(
        _CMD_BEGIN_SOT_REMEDIATION,
        help="Begin SoT remediation or skip",
    )
    sub.add_parser(
        _CMD_CHECK_SOT_REMEDIATION,
        help="Check SoT remediation complete",
    )
    sub.add_parser(
        _CMD_COMPLETE_ROUND,
        help="Finalize evaluation round and return summary payload",
    )
    sub.add_parser(
        _CMD_RESUME_DRAFTING,
        help="Transition Evaluating -> Drafting after complete-round",
    )

    args = parser.parse_args()
    project_root = args.project_root.resolve()
    cycle_id = args.cycle_id.strip()

    try:
        if args.command == _CMD_BEGIN_EVAL_ROUND:
            return _emit(begin_eval_round(cycle_id, project_root))
        if args.command == _CMD_BEGIN_DIMENSION:
            payload = begin_dimension(cycle_id, project_root, dim=args.dim)
            if payload.get("ok") and "dispatch_input" in payload:
                print(payload["dispatch_input"])
                return 0
            return _emit(payload)
        if args.command == _CMD_FINISH_DIMENSION_PROBE:
            return _emit(
                finish_dimension_probe(cycle_id, project_root, dim=args.dim),
            )
        if args.command == _CMD_CHECK_DIMENSION:
            return _emit(check_dimension(cycle_id, project_root, dim=args.dim))
        if args.command == _CMD_PROBE_COMPLETE:
            return _emit(probe_complete(cycle_id, project_root))
        if args.command == _CMD_BEGIN_ARTIFACT_REMEDIATION:
            payload = begin_artifact_remediation(cycle_id, project_root)
            return _emit(payload)
        if args.command == _CMD_CHECK_ARTIFACT_REMEDIATION:
            return _emit(check_artifact_remediation(cycle_id, project_root))
        if args.command == _CMD_BEGIN_SOT_REMEDIATION:
            payload = begin_sot_remediation(cycle_id, project_root)
            return _emit(payload)
        if args.command == _CMD_CHECK_SOT_REMEDIATION:
            return _emit(check_sot_remediation(cycle_id, project_root))
        if args.command == _CMD_COMPLETE_ROUND:
            return _emit(complete_round(cycle_id, project_root))
        if args.command == _CMD_RESUME_DRAFTING:
            return _emit(resume_drafting(cycle_id, project_root))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    sys.exit(_cli())
