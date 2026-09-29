#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for tasks/*/action-receipt.json.

An action receipt answers every acceptance criterion of the task with evidence.
The script checks coverage and shape; it cannot check that evidence is true.

CLI:
    python3 tc_action_receipt_schema.py --schema
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


_SCHEMA: list[dict] = [
    {"field": "version", "type": "int", "required": True,
     "description": "Schema version (currently 2)"},
    {"field": "task_id", "type": "string", "required": True,
     "description": "Task id matching the work order"},
    {"field": "goal", "type": "string", "required": True,
     "description": "Task title from the work order"},
    {"field": "effects", "type": "string", "required": True,
     "description": "read_only, or 'mutates: <systems>' as declared by the task"},
    {"field": "results", "type": "array", "required": True,
     "description": "One {criterion, evidence, met} per acceptance criterion"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}


def get_schema() -> list[dict]:
    return list(_SCHEMA)


def receipt_path(session_dir: Path, task_id: str) -> Path:
    return session_dir / "tasks" / task_id / "action-receipt.json"


def _norm(text: str) -> str:
    return " ".join(text.split())


def _validate_results(results: object, criteria: list[str]) -> list[str]:
    if not isinstance(results, list):
        return ["results must be a list"]
    errors: list[str] = []
    answered: list[str] = []
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            errors.append(f"results[{index}] must be an object")
            continue
        criterion = item.get("criterion")
        if not isinstance(criterion, str) or not criterion.strip():
            errors.append(f"results[{index}].criterion must be a non-empty string")
            continue
        answered.append(_norm(criterion))
        evidence = item.get("evidence")
        if not isinstance(evidence, str) or not evidence.strip():
            errors.append(f"results[{index}].evidence must be a non-empty string")
        if item.get("met") is not True:
            errors.append(f"results[{index}].met must be true")
    expected = [_norm(c) for c in criteria]
    for criterion in expected:
        if criterion not in answered:
            errors.append(f"no result for acceptance criterion: {criterion!r}")
    for criterion in sorted(set(answered) - set(expected)):
        errors.append(f"result names unknown acceptance criterion: {criterion!r}")
    if len(answered) != len(set(answered)):
        errors.append("results answer the same acceptance criterion more than once")
    return errors


def validate_receipt(data: dict, expected_task_id: str, criteria: list[str]) -> list[str]:
    errors: list[str] = []
    if not criteria:
        return ["task has no acceptance criteria"]
    for field in sorted(_REQUIRED_FIELDS):
        if field not in data:
            errors.append(f"missing required field: '{field}'")
    if "version" in data and data.get("version") != 2:
        errors.append("version must be 2")
    if "task_id" in data and data.get("task_id") != expected_task_id:
        errors.append(
            f"task_id mismatch: expected {expected_task_id!r}, got {data.get('task_id')!r}"
        )
    for field in ("goal", "effects"):
        if field in data and (not isinstance(data[field], str) or not data[field].strip()):
            errors.append(f"{field} must be a non-empty string")
    if "results" in data:
        errors.extend(_validate_results(data["results"], criteria))
    return errors


def load_receipt(path: Path, expected_task_id: str, criteria: list[str]) -> dict:
    if not path.exists():
        raise ValueError(f"action-receipt.json not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"action-receipt.json invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("action-receipt.json root must be an object")
    errors = validate_receipt(data, expected_task_id, criteria)
    if errors:
        raise ValueError(f"action-receipt.json invalid: {'; '.join(errors)}")
    return data


def save_receipt(path: Path, payload: dict, criteria: list[str]) -> Path:
    errors = validate_receipt(payload, str(payload.get("task_id", "")), criteria)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="action-receipt.json schema utilities")
    parser.add_argument("--schema", action="store_true")
    args = parser.parse_args()
    if args.schema:
        print(json.dumps(get_schema(), indent=2))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
