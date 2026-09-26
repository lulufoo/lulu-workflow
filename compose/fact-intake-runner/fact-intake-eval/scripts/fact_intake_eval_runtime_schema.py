#!/usr/bin/env python3
"""Fact-intake-eval runtime under ``{slice}/fact-intake-eval/`` (independent of delivery Evaluating)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FACT_INTAKE_EVAL_DIRNAME = "fact-intake-eval"
RUNTIME_FILENAME = "fact-intake-eval-runtime.json"
WORKFLOW_STATE_FILENAME = "fact-intake-eval-workflow-state.md"
MAX_EVAL_ROUNDS = 3


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fact_intake_eval_root(slice_dir: Path) -> Path:
    return slice_dir.resolve() / FACT_INTAKE_EVAL_DIRNAME


def runtime_path(slice_dir: Path) -> Path:
    return fact_intake_eval_root(slice_dir) / RUNTIME_FILENAME


def workflow_state_view_path(slice_dir: Path) -> Path:
    return fact_intake_eval_root(slice_dir) / WORKFLOW_STATE_FILENAME


def evaluate_state_path(slice_dir: Path) -> Path:
    return fact_intake_eval_root(slice_dir) / "evaluate-state.md"


def evaluate_dir(slice_dir: Path, evaluate_round: int) -> Path:
    return fact_intake_eval_root(slice_dir) / f"evaluate{int(evaluate_round)}"


def default_runtime() -> dict[str, Any]:
    return {
        "version": 1,
        "focus_phase": "pending",
        "evaluate_round": 0,
        "failure_count": 0,
        "last_outcome": "",
        "active_lease_id": "",
        "write_staging_dir": "",
        "max_rounds": MAX_EVAL_ROUNDS,
        "completion_mode": "return_to_caller",
        "updated_at": _now_iso(),
    }


def load_runtime(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_runtime()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"fact-intake-eval runtime must be an object: {path}")
    merged = default_runtime()
    merged.update(data)
    return merged


def save_runtime(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["updated_at"] = _now_iso()
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_workflow_state_view(runtime: dict[str, Any]) -> dict[str, str]:
    return {
        "version": "1",
        "workflow": "compose-fact-intake-eval",
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def enter_evaluating_runtime(runtime: dict[str, Any]) -> dict[str, Any]:
    updated = dict(runtime)
    current_round = int(updated.get("evaluate_round") or 0)
    if updated.get("focus_phase") == "evaluating":
        return updated
    updated["focus_phase"] = "evaluating"
    updated["evaluate_round"] = current_round + 1
    updated["last_outcome"] = ""
    return updated


def allocate_lease(slice_dir: Path, runtime: dict[str, Any]) -> dict[str, Any]:
    lease_id = uuid.uuid4().hex
    staging = fact_intake_eval_root(slice_dir) / "staging" / lease_id
    staging.mkdir(parents=True, exist_ok=True)
    updated = dict(runtime)
    updated["active_lease_id"] = lease_id
    updated["write_staging_dir"] = staging.resolve().as_posix()
    return updated


def hard_blocked(runtime: dict[str, Any]) -> bool:
    max_rounds = int(runtime.get("max_rounds") or MAX_EVAL_ROUNDS)
    return int(runtime.get("failure_count") or 0) >= max_rounds


def gate_allows_derive_from_evaluate_state(eval_data: dict[str, str]) -> bool:
    return str(eval_data.get("eval_status", "")).strip() == "done"


# Backward-compatible alias
atomize_eval_root = fact_intake_eval_root
