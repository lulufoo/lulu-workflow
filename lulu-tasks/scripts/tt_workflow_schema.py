#!/usr/bin/env python3
"""Read and write one lulu-tasks workflow-state.md."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tt_workflow_common import doc_dir, parse_frontmatter_fields

ALLOWED = {
    ("Drafting", "Evaluating"),
    ("Evaluating", "Drafting"),
    ("Evaluating", "ReadyForDelivery"),
    ("ReadyForDelivery", "Delivered"),
}


def workflow_file(project_root: Path, cycle_id: str, doc_round: int) -> Path:
    return project_root / doc_dir(cycle_id, doc_round) / "workflow-state.md"


def read_workflow_state(path: Path) -> dict[str, str | int]:
    if not path.is_file():
        raise FileNotFoundError(path)
    fields = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
    raw_round = fields.get("evaluate_round", "0")
    try:
        evaluate_round = int(raw_round)
    except ValueError as exc:
        raise ValueError(f"evaluate_round is not an integer: {raw_round!r}") from exc
    return {
        "current_state": fields.get("current_state", ""),
        "evaluate_round": evaluate_round,
        "tech_ref": fields.get("tech_ref", ""),
    }


def write_workflow_state(
    path: Path,
    *,
    current_state: str,
    evaluate_round: int,
    tech_ref: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    path.write_text(
        "---\n"
        "version: 1\n"
        "workflow: lulu-tasks\n"
        f"current_state: {current_state}\n"
        f"evaluate_round: {int(evaluate_round)}\n"
        f"tech_ref: {tech_ref}\n"
        f"updated_at: {now}\n"
        "---\n",
        encoding="utf-8",
    )


def transition_workflow(
    path: Path,
    to_state: str,
    *,
    evaluate_round: int | None = None,
) -> dict[str, str | int]:
    current = read_workflow_state(path)
    pair = (str(current["current_state"]), to_state)
    if pair not in ALLOWED:
        raise ValueError(f"cannot move from {pair[0]} to {to_state}")
    write_workflow_state(
        path,
        current_state=to_state,
        evaluate_round=current["evaluate_round"] if evaluate_round is None else evaluate_round,
        tech_ref=str(current["tech_ref"]),
    )
    return read_workflow_state(path)
