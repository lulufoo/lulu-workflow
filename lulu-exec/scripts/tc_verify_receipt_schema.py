#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for tasks/*/verify-receipt.json.

CLI:
    python3 tc_verify_receipt_schema.py --schema
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


_SCHEMA: list[dict] = [
    {"field": "version", "type": "int", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "task_id", "type": "string", "required": True,
     "description": "Task id matching the work order"},
    {"field": "command", "type": "string", "required": True,
     "description": "Command that was run"},
    {"field": "observed", "type": "string", "required": True,
     "description": "Observable result"},
    {"field": "ok", "type": "bool", "required": True,
     "description": "Whether the observable result matched"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}


def get_schema() -> list[dict]:
    return list(_SCHEMA)


def receipt_path(session_dir: Path, task_id: str) -> Path:
    return session_dir / "tasks" / task_id / "verify-receipt.json"


def validate_receipt(data: dict, expected_task_id: str) -> list[str]:
    errors: list[str] = []
    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")
    if "version" in data and data.get("version") != 1:
        errors.append("version must be 1")
    if "task_id" in data and data.get("task_id") != expected_task_id:
        errors.append(
            f"task_id mismatch: expected {expected_task_id!r}, got {data.get('task_id')!r}"
        )
    if "command" in data and (not isinstance(data["command"], str) or not data["command"].strip()):
        errors.append("command must be a non-empty string")
    if "observed" in data and (not isinstance(data["observed"], str) or not data["observed"].strip()):
        errors.append("observed must be a non-empty string")
    if "ok" in data and not isinstance(data["ok"], bool):
        errors.append("ok must be a boolean")
    return errors


def load_receipt(path: Path, expected_task_id: str) -> dict:
    if not path.exists():
        raise ValueError(f"verify-receipt.json not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"verify-receipt.json invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("verify-receipt.json root must be an object")
    errors = validate_receipt(data, expected_task_id)
    if errors:
        raise ValueError(f"verify-receipt.json invalid: {'; '.join(errors)}")
    if data.get("ok") is not True:
        raise ValueError("verify-receipt.json ok is not true")
    return data


def save_receipt(path: Path, payload: dict) -> Path:
    errors = validate_receipt(payload, str(payload.get("task_id", "")))
    if errors:
        raise ValueError("; ".join(errors))
    if payload.get("ok") is not True:
        raise ValueError("receipt ok must be true")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="verify-receipt.json schema utilities")
    parser.add_argument("--schema", action="store_true")
    args = parser.parse_args()
    if args.schema:
        print(json.dumps(get_schema(), indent=2))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
