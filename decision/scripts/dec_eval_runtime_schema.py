#!/usr/bin/env python3
"""Decision-owned Eval runtime state (maps onto Eval Working/evaluating).

Pass flag is last_outcome == "pass". No failure_count / max_rounds.
Design: docs/domain/archive/decision/decision-eval-pass-flag-replace-round-limit.md
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dec_io import atomic_write_text

RUNTIME_FILENAME = "decision-eval-runtime.json"
EVAL_WORKFLOW_STATE_FILENAME = "decision-eval-workflow-state.md"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def runtime_path(session_dir: Path) -> Path:
    return session_dir / RUNTIME_FILENAME


def workflow_state_path(session_dir: Path) -> Path:
    return session_dir / EVAL_WORKFLOW_STATE_FILENAME


def evaluate_state_path(session_dir: Path) -> Path:
    return session_dir / "eval" / "evaluate-state.md"


def evaluate_dir(session_dir: Path, evaluate_round: int) -> Path:
    return session_dir / "eval" / f"round-{int(evaluate_round)}"


def default_runtime() -> dict[str, Any]:
    return {
        "version": 1,
        "focus_phase": "pending",
        "evaluate_round": 0,
        "last_outcome": "",
        "active_lease_id": "",
        "write_staging_dir": "",
        "updated_at": _now_iso(),
    }


def load_runtime(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_runtime()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"decision eval runtime must be an object: {path}")
    merged = default_runtime()
    merged.update(data)
    merged.pop("failure_count", None)
    return merged


def save_runtime(path: Path, data: dict[str, Any]) -> None:
    payload = dict(data)
    payload.pop("failure_count", None)
    payload["updated_at"] = _now_iso()
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def load_workflow_state_view(runtime: dict[str, Any]) -> dict[str, str]:
    """Synthetic Compose-shaped fields for shared Eval control."""
    return {
        "version": "1",
        "workflow": "lulu-decision",
        "mode": "tech",
        "cycle_type": "feature",
        "current_state": "Working",
        "evaluate_round": str(int(runtime.get("evaluate_round") or 0)),
        "updated_at": str(runtime.get("updated_at") or _now_iso()),
    }


def write_workflow_state_file(path: Path, runtime: dict[str, Any]) -> None:
    view = load_workflow_state_view(runtime)
    lines = ["---"]
    for key, value in view.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    atomic_write_text(path, "\n".join(lines))


def enter_evaluating_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    updated = dict(runtime)
    current_round = int(updated.get("evaluate_round") or 0)
    if updated.get("focus_phase") == "evaluating":
        return updated
    updated["focus_phase"] = "evaluating"
    updated["evaluate_round"] = current_round + 1
    updated["last_outcome"] = ""
    return updated


def exit_evaluating_runtime(
    runtime: dict[str, Any],
    *,
    outcome: str,
) -> dict[str, Any]:
    updated = dict(runtime)
    updated["focus_phase"] = "pending"
    updated["active_lease_id"] = ""
    updated["write_staging_dir"] = ""
    updated["last_outcome"] = outcome
    updated.pop("failure_count", None)
    return updated


def allocate_lease(session_dir: Path, runtime: dict[str, Any]) -> dict[str, Any]:
    lease_id = uuid.uuid4().hex
    staging = session_dir / "eval" / "staging" / lease_id
    staging.mkdir(parents=True, exist_ok=True)
    updated = dict(runtime)
    updated["active_lease_id"] = lease_id
    updated["write_staging_dir"] = staging.resolve().as_posix()
    return updated


