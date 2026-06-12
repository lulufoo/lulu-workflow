#!/usr/bin/env python3
"""Read-only session info facade for tech-plan orchestrator.

Aggregates schema modules for SKILL-facing reads. No state mutations.

CLI:
    python3 session_info.py --cycle-id <id> --project-root . \\
        [--view delivery-preview|session|stage-transitions|eval-dispatch|eval-summary]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from evaluate_state_schema import (  # noqa: E402
    load_evaluate_state,
    resolve_evaluate_state_path_from_cycle,
)
from hook_guard import load_transitions  # noqa: E402
from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from tech_doc_schema import load_presentation_from_cycle  # noqa: E402
from workflow_common import STAGE, detect_cycle_type, eval_round_dir  # noqa: E402
from workflow_state_schema import (  # noqa: E402
    load_workflow_state,
    resolve_workflow_state_path_from_cycle,
)
from eval_control import dispatch_list  # noqa: E402

_VIEW_DELIVERY_PREVIEW = "delivery-preview"
_VIEW_SESSION = "session"
_VIEW_STAGE_TRANSITIONS = "stage-transitions"
_VIEW_EVAL_DISPATCH = "eval-dispatch"
_VIEW_EVAL_SUMMARY = "eval-summary"
_CMD_DELIVERY_PREVIEW = "delivery-preview"
_CMD_EVAL_DISPATCH = "eval-dispatch"
_CMD_EVAL_SUMMARY = "eval-summary"
_EXPECTED_DELIVERY_PREVIEW_STATE = "ReadyForDelivery"
_EXPECTED_EVAL_DISPATCH_STATE = "Evaluating"
_EXPECTED_EVAL_SUMMARY_STATE = "Evaluating"
_DIM_INDEX_TO_NAME = {"1": "e1", "2": "e2", "3": "e3"}
_REVIEW_FILE_RE = re.compile(r"tech-review-e\d+([123])\.md$")
_VALID_VIEWS = frozenset({
    _VIEW_DELIVERY_PREVIEW,
    _VIEW_SESSION,
    _VIEW_STAGE_TRANSITIONS,
    _VIEW_EVAL_DISPATCH,
    _VIEW_EVAL_SUMMARY,
})


def _delivery_preview_failure(current_state: str) -> dict[str, Any]:
    return {
        "ok": False,
        "command": _CMD_DELIVERY_PREVIEW,
        "current_state": current_state,
        "message": (
            f"delivery-preview rejected: current state is {current_state}, "
            f"expected {_EXPECTED_DELIVERY_PREVIEW_STATE}. "
            "Pause execution and wait for user direction."
        ),
    }


def _eval_dispatch_failure(
    current_state: str,
    *,
    reason: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "command": _CMD_EVAL_DISPATCH,
        "current_state": current_state,
        "message": (
            f"eval-dispatch rejected: {reason} "
            "Pause execution and wait for user direction."
        ),
    }


def _eval_summary_failure(
    current_state: str,
    *,
    reason: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "command": _CMD_EVAL_SUMMARY,
        "current_state": current_state,
        "message": (
            f"eval-summary rejected: {reason} "
            "Pause execution and wait for user direction."
        ),
    }


def _split_table_row(line: str) -> list[str]:
    cells = line.strip().split("|")
    if len(cells) >= 3:
        return [cell.strip() for cell in cells[1:-1]]
    return [cell.strip() for cell in cells if cell.strip()]


def _parse_review_issues(path: Path, *, dimension: str) -> list[dict[str, str]]:
    """Parse eval-runner review table rows from a tech-review markdown file."""
    if not path.exists():
        return []

    issues: list[dict[str, str]] = []
    header: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = _split_table_row(line)
        if not cells:
            continue
        lowered = [cell.lower() for cell in cells]
        if "severity" in lowered and "status" in lowered and "decision" in lowered:
            header = lowered
            continue
        if not header:
            continue

        row = {header[i]: cells[i] if i < len(cells) else "" for i in range(len(header))}

        issue_id = row.get("id") or row.get("#") or ""
        description = row.get("description") or row.get("issue") or ""
        if not issue_id and not description:
            continue

        issues.append({
            "id": issue_id,
            "dimension": dimension,
            "location": row.get("location", ""),
            "severity": row.get("severity", ""),
            "description": description,
            "status": row.get("status", ""),
            "decision": row.get("decision", ""),
        })
    return issues


def _dimension_from_review_path(path: Path) -> str:
    match = _REVIEW_FILE_RE.search(path.name)
    if not match:
        return ""
    return _DIM_INDEX_TO_NAME.get(match.group(1), "")


def _collect_review_issues(eval_dir: Path) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[dict[str, str]] = []
    review_paths: list[str] = []
    if not eval_dir.is_dir():
        return issues, review_paths

    for path in sorted(eval_dir.glob("tech-review-e*.md")):
        dimension = _dimension_from_review_path(path)
        if not dimension:
            continue
        review_paths.append(path.as_posix())
        issues.extend(_parse_review_issues(path, dimension=dimension))
    return issues, review_paths


def _build_dimensions(eval_state: dict[str, str]) -> list[dict[str, str]]:
    dimensions: list[dict[str, str]] = []
    for dim in ("e1", "e2", "e3"):
        status = eval_state.get(f"{dim}_status", "")
        if status in ("", "pending"):
            continue
        dimensions.append({
            "dim": dim,
            "status": status,
            "total": eval_state.get(f"{dim}_total_issues", "0"),
            "resolved": eval_state.get(f"{dim}_resolved_issues", "0"),
        })
    return dimensions


def _count_ignored(issues: list[dict[str, str]]) -> int:
    return sum(1 for issue in issues if issue.get("decision", "").lower() == "ignore")


def eval_dispatch(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Return eval dimension dispatch sequence for Evaluating Phase 2."""
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current != _EXPECTED_EVAL_DISPATCH_STATE:
        return _eval_dispatch_failure(
            current,
            reason=(
                f"current state is {current!r}, "
                f"expected {_EXPECTED_EVAL_DISPATCH_STATE!r}."
            ),
        )

    try:
        evaluate_round = int(state.get("evaluate_round", "0"))
    except ValueError:
        evaluate_round = 0
    if evaluate_round < 1:
        return _eval_dispatch_failure(
            current,
            reason=f"evaluate_round is {evaluate_round!r} (expected >= 1).",
        )

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    if not es_path.exists():
        return _eval_dispatch_failure(current, reason="evaluate-state.md not found.")

    mode = state["mode"]
    return {
        "ok": True,
        "view": _VIEW_EVAL_DISPATCH,
        "current_state": current,
        "mode": mode,
        "dispatch": dispatch_list(mode),
        "evaluate_round": evaluate_round,
        "active_doc": load_active_doc_from_cycle(cycle_id, project_root),
    }


def eval_summary(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Return aggregated evaluation results for Evaluating Phase 4 presentation."""
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    current = state["current_state"]

    if current != _EXPECTED_EVAL_SUMMARY_STATE:
        return _eval_summary_failure(
            current,
            reason=(
                f"current state is {current!r}, "
                f"expected {_EXPECTED_EVAL_SUMMARY_STATE!r}."
            ),
        )

    try:
        evaluate_round = int(state.get("evaluate_round", "0"))
    except ValueError:
        evaluate_round = 0
    if evaluate_round < 1:
        return _eval_summary_failure(
            current,
            reason=f"evaluate_round is {evaluate_round!r} (expected >= 1).",
        )

    es_path = resolve_evaluate_state_path_from_cycle(cycle_id, project_root)
    if not es_path.exists():
        return _eval_summary_failure(current, reason="evaluate-state.md not found.")

    eval_state = load_evaluate_state(es_path)
    current_dimension = eval_state.get("current_dimension", "")
    if current_dimension != "done":
        return _eval_summary_failure(
            current,
            reason=(
                f"current_dimension is {current_dimension!r} (expected 'done')."
            ),
        )

    active_doc = load_active_doc_from_cycle(cycle_id, project_root)
    eval_dir = project_root / eval_round_dir(cycle_id, active_doc, evaluate_round)
    issues, review_paths = _collect_review_issues(eval_dir)

    total_issues = int(eval_state.get("total_issues", "0") or "0")
    resolved_issues = int(eval_state.get("resolved_issues", "0") or "0")
    ignored_issues = _count_ignored(issues)
    if ignored_issues == 0 and total_issues > resolved_issues:
        ignored_issues = total_issues - resolved_issues

    return {
        "ok": True,
        "view": _VIEW_EVAL_SUMMARY,
        "evaluate_round": evaluate_round,
        "current_state": current,
        "current_dimension": current_dimension,
        "fix_severity": eval_state.get("fix_severity", ""),
        "fix_severity_reason": eval_state.get("fix_severity_reason", ""),
        "counts": {
            "total_issues": total_issues,
            "resolved_issues": resolved_issues,
            "ignored_issues": ignored_issues,
        },
        "dimensions": _build_dimensions(eval_state),
        "issues": issues,
        "review_paths": review_paths,
    }


def delivery_preview(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Return fields needed to present tech-doc before delivery confirmation."""
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    current = state["current_state"]
    if current != _EXPECTED_DELIVERY_PREVIEW_STATE:
        return _delivery_preview_failure(current)

    tech_doc = load_presentation_from_cycle(cycle_id, project_root)
    return {
        "ok": True,
        "view": _VIEW_DELIVERY_PREVIEW,
        "active_doc": load_active_doc_from_cycle(cycle_id, project_root),
        "current_state": current,
        "tech_doc": {
            "path": tech_doc["path"],
            "title": tech_doc["title"],
            "summary": tech_doc["summary"],
        },
    }


def stage_transitions(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Return allowed next stages from transition-table.json for this stage."""
    cycle_type = detect_cycle_type(cycle_id)
    transitions = load_transitions(cycle_type)
    next_stages = sorted(transitions.get(STAGE, set()))
    return {"next_stages": next_stages}


def session_snapshot(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Return workflow state plus tech-doc presentation for session resume."""
    ws_path = resolve_workflow_state_path_from_cycle(cycle_id, project_root)
    state = load_workflow_state(ws_path)
    tech_doc = load_presentation_from_cycle(cycle_id, project_root)
    return {
        "view": _VIEW_SESSION,
        "active_doc": load_active_doc_from_cycle(cycle_id, project_root),
        "workflow_state": {
            "current_state": state["current_state"],
            "mode": state.get("mode", ""),
            "evaluate_round": state.get("evaluate_round", "0"),
            "product_ref": state.get("product_ref", ""),
            "carry_forward_ref": state.get("carry_forward_ref", ""),
        },
        "tech_doc": {
            "path": tech_doc["path"],
            "title": tech_doc["title"],
            "summary": tech_doc["summary"],
            "revision": tech_doc["revision"],
        },
    }


def get_session_info(
    cycle_id: str,
    project_root: Path,
    *,
    view: str = _VIEW_DELIVERY_PREVIEW,
) -> dict[str, Any]:
    if view not in _VALID_VIEWS:
        raise ValueError(f"unknown view: {view!r} (allowed: {sorted(_VALID_VIEWS)})")
    if view == _VIEW_SESSION:
        return session_snapshot(cycle_id, project_root)
    if view == _VIEW_STAGE_TRANSITIONS:
        return stage_transitions(cycle_id, project_root)
    if view == _VIEW_EVAL_DISPATCH:
        return eval_dispatch(cycle_id, project_root)
    if view == _VIEW_EVAL_SUMMARY:
        return eval_summary(cycle_id, project_root)
    return delivery_preview(cycle_id, project_root)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="tech-plan read-only session info")
    parser.add_argument("--cycle-id", required=True, help="Cycle ID")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root directory",
    )
    parser.add_argument(
        "--view",
        choices=sorted(_VALID_VIEWS),
        default=_VIEW_DELIVERY_PREVIEW,
        help="Info slice to return (default: delivery-preview)",
    )
    args = parser.parse_args()

    try:
        payload = get_session_info(
            args.cycle_id.strip(),
            args.project_root.resolve(),
            view=args.view,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(_cli())
