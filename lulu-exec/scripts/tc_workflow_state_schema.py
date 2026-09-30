#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for lulu-exec workflow-state.md.

CLI:
    python3 workflow_state_schema.py --schema
    python3 workflow_state_schema.py --read  --path <workflow-state.md>
    python3 workflow_state_schema.py --read  --cycle-dir <cycle-cache-dir>
    python3 workflow_state_schema.py --write --path <workflow-state.md> --json '<object>'
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tc_session_state_schema import load_session_state
from tc_workflow_common import exec_stage_dir, parse_frontmatter_fields
from stage_identity import EXEC_STAGE

_WHITELIST_PATH = Path(__file__).resolve().parents[1] / "transition-whitelist.json"

_SCHEMA: list[dict] = [
    {"field": "version", "type": "string", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "workflow", "type": "string", "required": True,
     "description": "Fixed value: lulu-exec"},
    {"field": "current_state", "type": "string", "required": True,
     "description": "Session state: Starting / Preparing / Executing / Closing / Delivered"},
    {"field": "mode", "type": "string", "required": True,
     "description": "Execution mode (may be empty)"},
    {"field": "task_list_ref", "type": "string", "required": True,
     "description": "Path to code-task-list.md (may be empty)"},
    {"field": "current_task", "type": "string", "required": True,
     "description": "Active task id (may be empty)"},
    {"field": "current_phase", "type": "string", "required": True,
     "description": "Task phase (empty or whitelist task state)"},
    {"field": "updated_at", "type": "string", "required": True,
     "description": "ISO 8601 last-update timestamp"},
    {"field": "historical", "type": "string", "required": False,
     "description": "Set to true when session is superseded by reopen"},
    {"field": "master_conversation_id", "type": "string", "required": False,
     "description": "conversation_id of the orchestrating session that ran Starting"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}
_OPTIONAL_SCHEMA_FIELDS = {s["field"] for s in _SCHEMA if not s["required"]}
_SCHEMA_FIELD_NAMES = _REQUIRED_FIELDS | _OPTIONAL_SCHEMA_FIELDS

_REQUIRED_KEY_ORDER = [
    "version",
    "workflow",
    "current_state",
    "mode",
    "task_list_ref",
    "current_task",
    "current_phase",
    "updated_at",
]

_whitelist_cache: Optional[dict] = None


def _load_whitelist() -> dict:
    global _whitelist_cache
    if _whitelist_cache is None:
        _whitelist_cache = json.loads(_WHITELIST_PATH.read_text(encoding="utf-8"))
    return _whitelist_cache


def get_schema() -> list[dict]:
    """Return field definitions for workflow-state.md."""
    return list(_SCHEMA)


def validate_workflow_state(data: dict) -> list[str]:
    """Return list of validation error strings; empty means valid."""
    errors: list[str] = []
    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")

    if "version" in data and data["version"] != "1":
        errors.append(f"invalid version: {data['version']!r} (expected '1')")

    if "workflow" in data and data["workflow"] != EXEC_STAGE:
        errors.append(
            f"invalid workflow: {data['workflow']!r} (expected '{EXEC_STAGE}')"
        )

    whitelist = _load_whitelist()
    session_states = set(whitelist["session"]["states"])
    task_states = set(whitelist["task"]["states"])

    if "current_state" in data and data["current_state"] not in session_states:
        errors.append(
            f"invalid current_state: {data['current_state']!r} "
            f"(allowed: {sorted(session_states)})"
        )

    phase = data.get("current_phase", "")
    if phase and phase not in task_states:
        errors.append(
            f"invalid current_phase: {phase!r} (allowed: {sorted(task_states)} or empty)"
        )

    return errors


def load_workflow_state(path: Path) -> dict:
    """Read and validate workflow-state.md; raise ValueError if missing or invalid."""
    if not path.exists():
        raise ValueError(f"workflow-state.md not found: {path}")
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        raise ValueError(f"missing YAML frontmatter in {path}")
    fields = parse_frontmatter_fields(content)
    if not fields:
        raise ValueError(f"empty or invalid frontmatter in {path}")
    errors = validate_workflow_state(fields)
    if errors:
        raise ValueError(f"workflow-state.md invalid ({path}): {'; '.join(errors)}")
    return fields


def _serialize_frontmatter(data: dict) -> str:
    lines = ["---"]
    for key in _REQUIRED_KEY_ORDER:
        if key in data:
            lines.append(f"{key}: {data[key]}")
    for key in sorted(_OPTIONAL_SCHEMA_FIELDS):
        if key in data:
            lines.append(f"{key}: {data[key]}")
    for key, value in data.items():
        if key not in _SCHEMA_FIELD_NAMES:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def save_workflow_state(path: Path, data: dict, *, merge: bool = True) -> None:
    """Write workflow-state.md with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and merge:
        existing = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
        merged = dict(existing)
        merged.update(data)
        if "historical" not in data and "historical" in existing:
            merged["historical"] = existing["historical"]
        data = merged

    data = dict(data)
    data["updated_at"] = datetime.now(timezone.utc).isoformat()

    errors = validate_workflow_state(data)
    if errors:
        raise ValueError(f"workflow-state data invalid: {'; '.join(errors)}")

    path.write_text(_serialize_frontmatter(data), encoding="utf-8")


def resolve_workflow_state_path(cycle_dir: Path) -> Path:
    """Resolve s{N}/workflow-state.md from cycle cache dir via session-state.md."""
    code_dir = exec_stage_dir(cycle_dir)
    active = load_session_state(code_dir / "session-state.md")
    return code_dir / f"s{active}" / "workflow-state.md"


def init_starting(
    path: Path,
    *,
    mode: str,
    task_list_ref: str,
    master_conversation_id: str = "",
) -> None:
    """Initialize workflow-state.md in Starting state."""
    data = {
        "version": "1",
        "workflow": EXEC_STAGE,
        "current_state": "Starting",
        "mode": mode,
        "task_list_ref": task_list_ref,
        "current_task": "",
        "current_phase": "",
    }
    if master_conversation_id:
        data["master_conversation_id"] = master_conversation_id
    save_workflow_state(path, data, merge=False)


def init_preparing(path: Path, *, mode: str, task_list_ref: str) -> None:
    """Initialize a new workflow-state.md in Preparing state."""
    data = {
        "version": "1",
        "workflow": EXEC_STAGE,
        "current_state": "Preparing",
        "mode": mode,
        "task_list_ref": task_list_ref,
        "current_task": "",
        "current_phase": "",
    }
    save_workflow_state(path, data, merge=False)


def mark_historical(path: Path) -> None:
    """Mark an existing workflow-state.md as historical (idempotent)."""
    if not path.exists():
        return
    fields = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
    if fields.get("historical") == "true":
        return
    fields["historical"] = "true"
    for key, default in (
        ("version", "1"),
        ("workflow", EXEC_STAGE),
        ("mode", ""),
        ("task_list_ref", ""),
        ("current_task", ""),
        ("current_phase", ""),
    ):
        fields.setdefault(key, default)
    save_workflow_state(path, fields, merge=False)


def _cli() -> int:
    p = argparse.ArgumentParser(description="workflow-state.md schema utilities")
    p.add_argument("--schema", action="store_true", help="Print JSON schema array and exit")
    p.add_argument("--read", action="store_true", help="Print workflow state as JSON")
    p.add_argument("--write", action="store_true", help="Write workflow state from --json")
    p.add_argument("--path", type=Path, help="Path to workflow-state.md")
    p.add_argument("--cycle-dir", type=Path, help="Cycle cache directory")
    p.add_argument("--json", type=str, help="JSON object for --write")
    args = p.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    if args.read:
        if args.cycle_dir:
            path = resolve_workflow_state_path(args.cycle_dir)
        elif args.path:
            path = args.path
        else:
            p.error("--read requires --path or --cycle-dir")
        try:
            data = load_workflow_state(path)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    if args.write:
        if not args.path:
            p.error("--write requires --path")
        if not args.json:
            p.error("--write requires --json")
        try:
            data = json.loads(args.json)
        except json.JSONDecodeError as exc:
            print(f"invalid JSON: {exc}", file=sys.stderr)
            return 1
        if not isinstance(data, dict):
            print("--json must be a JSON object", file=sys.stderr)
            return 1
        try:
            save_workflow_state(args.path, data)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        return 0

    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
