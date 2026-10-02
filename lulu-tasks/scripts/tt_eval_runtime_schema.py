#!/usr/bin/env python3
"""lulu-tasks Eval runtime. One round probes every dimension; the parent owns Drafting."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_FILENAME = "tasks-eval-runtime.json"
EVAL_WORKFLOW_STATE_FILENAME = "tasks-eval-workflow-state.md"
DIMENSIONS = (
    "compliance-crosscheck",
    "execution-admission",
)
_LEGACY_KEYS = ("phase", "probing_phase")


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
        "pass_id": 0,
        "last_outcome": "",
        "last_disposition": "",
        "last_issues": [],
        "active_lease_id": "",
        "write_staging_dir": "",
        "updated_at": _now_iso(),
    }


def load_runtime(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_runtime()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"tasks eval runtime must be an object: {path}")
    merged = default_runtime()
    merged.update(data)
    for key in _LEGACY_KEYS:
        merged.pop(key, None)
    if not isinstance(merged.get("last_issues"), list):
        merged["last_issues"] = []
    return merged


def save_runtime(path: Path, data: dict[str, Any]) -> None:
    payload = dict(data)
    payload["updated_at"] = _now_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_workflow_state_view(runtime: dict[str, Any]) -> dict[str, str]:
    return {
        "version": "1",
        "workflow": "lulu-tasks",
        "mode": "tech",
        "cycle_type": "feature",
        "current_state": "Working",
        "evaluate_round": str(int(runtime.get("evaluate_round") or 0)),
        "updated_at": str(runtime.get("updated_at") or _now_iso()),
    }


def write_workflow_state_file(path: Path, runtime: dict[str, Any]) -> None:
    view = load_workflow_state_view(runtime)
    lines = ["---", *[f"{key}: {value}" for key, value in view.items()], "---", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def enter_evaluating_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    updated = dict(runtime)
    if updated.get("focus_phase") == "evaluating":
        return updated
    updated["focus_phase"] = "evaluating"
    updated["evaluate_round"] = int(updated.get("evaluate_round") or 0) + 1
    updated["last_outcome"] = ""
    return updated


def exit_evaluating_runtime(runtime: dict[str, Any], *, outcome: str) -> dict[str, Any]:
    updated = dict(runtime)
    updated["focus_phase"] = "pending"
    updated["active_lease_id"] = ""
    updated["write_staging_dir"] = ""
    updated["last_outcome"] = outcome
    return updated


def allocate_lease(session_dir: Path, runtime: dict[str, Any]) -> dict[str, Any]:
    lease_id = uuid.uuid4().hex
    staging = session_dir / "eval" / "staging" / lease_id
    staging.mkdir(parents=True, exist_ok=True)
    updated = dict(runtime)
    updated["active_lease_id"] = lease_id
    updated["write_staging_dir"] = staging.resolve().as_posix()
    return updated
