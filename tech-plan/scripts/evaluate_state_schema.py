#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for tech-plan evaluate-state.md (v2).

CLI:
    python3 evaluate_state_schema.py --schema
    python3 evaluate_state_schema.py --read  --path <evaluate-state.md>
"""

from __future__ import annotations

import argparse
import fcntl
import json
import sys
from collections.abc import Callable
from pathlib import Path

from session_state_schema import load_active_doc_from_cycle
from workflow_common import doc_dir, parse_frontmatter_fields

_SCHEMA: list[dict] = [
    {"field": "version", "type": "string", "required": True,
     "description": "Schema version (currently 2)"},
    {"field": "phase", "type": "string", "required": True,
     "description": "Fixed value: evaluate"},
    {"field": "eval_status", "type": "string", "required": True,
     "description": "Round-level status: active | done | abandoned"},
    {"field": "fix_phase", "type": "string", "required": True,
     "description": "probe | artifact-remediation | sot-remediation | done"},
    {"field": "current_dimension", "type": "string", "required": True,
     "description": "JSON map of dim -> pending|in_progress|probed|complete"},
    {"field": "e1_total_issues", "type": "string", "required": True,
     "description": "e1 total issues count"},
    {"field": "e1_resolved_issues", "type": "string", "required": True,
     "description": "e1 resolved issues count"},
    {"field": "e2_total_issues", "type": "string", "required": True,
     "description": "e2 total issues count"},
    {"field": "e2_resolved_issues", "type": "string", "required": True,
     "description": "e2 resolved issues count"},
    {"field": "e3_total_issues", "type": "string", "required": True,
     "description": "e3 total issues count"},
    {"field": "e3_resolved_issues", "type": "string", "required": True,
     "description": "e3 resolved issues count"},
    {"field": "total_issues", "type": "string", "required": True,
     "description": "Aggregate total issues"},
    {"field": "resolved_issues", "type": "string", "required": True,
     "description": "Aggregate resolved issues"},
    {"field": "fix_severity", "type": "string", "required": True,
     "description": "Highest severity from completed eval round summary"},
    {"field": "fix_severity_reason", "type": "string", "required": True,
     "description": "Fix severity reason"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}
_SCHEMA_FIELD_NAMES = _REQUIRED_FIELDS

_KEY_ORDER = [
    "version",
    "phase",
    "eval_status",
    "fix_phase",
    "current_dimension",
    "e1_total_issues",
    "e1_resolved_issues",
    "e2_total_issues",
    "e2_resolved_issues",
    "e3_total_issues",
    "e3_resolved_issues",
    "total_issues",
    "resolved_issues",
    "fix_severity",
    "fix_severity_reason",
]

_VALID_MODES = frozenset({"product", "tech"})
_VALID_EVAL_STATUS = frozenset({"active", "done", "abandoned"})
_VALID_FIX_PHASE = frozenset({
    "probe",
    "artifact-remediation",
    "sot-remediation",
    "done",
})
_VALID_DIM_STATUS = frozenset({"pending", "in_progress", "probed", "complete"})
_DIM_STATUS_ORDER = {
    "pending": 0,
    "in_progress": 1,
    "probed": 2,
    "complete": 3,
}
_DISPATCH_BY_MODE = {"product": ["e1", "e2", "e3"], "tech": ["e2", "e3"]}


def dispatch_dims(mode: str) -> list[str]:
    """Return dispatch dimension list for workflow mode."""
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid mode: {mode!r} (allowed: {sorted(_VALID_MODES)})")
    return list(_DISPATCH_BY_MODE[mode])


def get_schema() -> list[dict]:
    """Return field definitions for evaluate-state.md."""
    return list(_SCHEMA)


def _base_fields() -> dict[str, str]:
    return {
        "version": "2",
        "phase": "evaluate",
        "eval_status": "active",
        "fix_phase": "probe",
        "e1_total_issues": "0",
        "e1_resolved_issues": "0",
        "e2_total_issues": "0",
        "e2_resolved_issues": "0",
        "e3_total_issues": "0",
        "e3_resolved_issues": "0",
        "total_issues": "0",
        "resolved_issues": "0",
        "fix_severity": "",
        "fix_severity_reason": "",
    }


def _initial_dimension_map(mode: str) -> dict[str, str]:
    return {dim: "pending" for dim in dispatch_dims(mode)}


def parse_current_dimension(raw: str) -> dict[str, str]:
    """Parse current_dimension JSON string to dim -> status map."""
    if not raw or raw.strip() == "":
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid current_dimension JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("current_dimension must be a JSON object")
    result: dict[str, str] = {}
    for key, value in parsed.items():
        status = str(value)
        if status not in _VALID_DIM_STATUS:
            raise ValueError(f"invalid dimension status for {key!r}: {status!r}")
        result[str(key)] = status
    return result


def serialize_current_dimension(dim_map: dict[str, str]) -> str:
    """Serialize dimension map to JSON string for frontmatter."""
    return json.dumps(dim_map, separators=(",", ":"))


def merge_current_dimension(
    data: dict[str, str],
    dim: str,
    status: str,
) -> dict[str, str]:
    """Patch one key in current_dimension map; return updated frontmatter dict."""
    if status not in _VALID_DIM_STATUS:
        raise ValueError(f"invalid dimension status: {status!r}")
    dim_map = parse_current_dimension(data.get("current_dimension", "{}"))
    dim_map[dim] = status
    merged = dict(data)
    merged["current_dimension"] = serialize_current_dimension(dim_map)
    return merged


def all_dims_at_least(
    data: dict[str, str],
    dispatch: list[str],
    min_status: str,
) -> bool:
    """Return True when every dispatch dim is at or past min_status."""
    if min_status not in _VALID_DIM_STATUS:
        raise ValueError(f"invalid min_status: {min_status!r}")
    min_rank = _DIM_STATUS_ORDER[min_status]
    dim_map = parse_current_dimension(data.get("current_dimension", "{}"))
    for dim in dispatch:
        status = dim_map.get(dim, "pending")
        if _DIM_STATUS_ORDER.get(status, -1) < min_rank:
            return False
    return True


def is_v2_state(data: dict[str, str]) -> bool:
    """Return True when evaluate-state uses v2 schema."""
    return data.get("version") == "2" and "fix_phase" in data


def build_initial_evaluate_state(*, mode: str) -> dict[str, str]:
    """Return frontmatter fields for a new evaluate-state.md."""
    if mode not in _VALID_MODES:
        raise ValueError(f"invalid mode: {mode!r} (allowed: {sorted(_VALID_MODES)})")

    data = _base_fields()
    dim_map = _initial_dimension_map(mode)
    data["current_dimension"] = serialize_current_dimension(dim_map)
    return data


def validate_evaluate_state(data: dict) -> list[str]:
    """Return list of validation error strings; empty means valid."""
    errors: list[str] = []
    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")
    if data.get("version") not in (None, "2"):
        errors.append(f"invalid version: {data.get('version')!r} (expected '2')")
    if data.get("phase") not in (None, "evaluate"):
        errors.append(f"invalid phase: {data.get('phase')!r} (expected 'evaluate')")
    eval_status = data.get("eval_status", "")
    if eval_status and eval_status not in _VALID_EVAL_STATUS:
        errors.append(f"invalid eval_status: {eval_status!r}")
    fix_phase = data.get("fix_phase", "")
    if fix_phase and fix_phase not in _VALID_FIX_PHASE:
        errors.append(f"invalid fix_phase: {fix_phase!r}")
    raw_dim = data.get("current_dimension", "")
    if raw_dim:
        try:
            dim_map = parse_current_dimension(raw_dim)
        except ValueError as exc:
            errors.append(str(exc))
        else:
            for dim, status in dim_map.items():
                if status not in _VALID_DIM_STATUS:
                    errors.append(f"invalid status for {dim}: {status!r}")
    return errors


def _serialize_frontmatter(data: dict) -> str:
    lines = ["---"]
    for key in _KEY_ORDER:
        if key in data:
            lines.append(f"{key}: {data[key]}")
    for key, value in data.items():
        if key not in _SCHEMA_FIELD_NAMES:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def save_evaluate_state(path: Path, data: dict, *, merge: bool = True) -> None:
    """Write evaluate-state.md with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and merge:
        existing = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
        merged = dict(existing)
        merged.update(data)
        data = merged

    errors = validate_evaluate_state(data)
    if errors:
        raise ValueError(f"evaluate-state data invalid: {'; '.join(errors)}")

    path.write_text(_serialize_frontmatter(data), encoding="utf-8")


def save_evaluate_state_locked(
    path: Path,
    patch_fn: Callable[[dict[str, str]], dict[str, str]],
) -> dict[str, str]:
    """Read-merge-validate-write evaluate-state under file lock."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.touch(exist_ok=True)

    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if path.exists():
                existing = parse_frontmatter_fields(
                    path.read_text(encoding="utf-8"),
                )
                data = patch_fn(dict(existing))
            else:
                data = patch_fn({})

            errors = validate_evaluate_state(data)
            if errors:
                raise ValueError(
                    f"evaluate-state data invalid: {'; '.join(errors)}"
                )
            path.write_text(_serialize_frontmatter(data), encoding="utf-8")
            return data
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def load_evaluate_state(path: Path) -> dict:
    """Read and validate evaluate-state.md."""
    if not path.exists():
        raise ValueError(f"evaluate-state.md not found: {path}")
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        raise ValueError(f"missing YAML frontmatter in {path}")
    fields = parse_frontmatter_fields(content)
    if not fields:
        raise ValueError(f"empty or invalid frontmatter in {path}")
    errors = validate_evaluate_state(fields)
    if errors:
        raise ValueError(f"evaluate-state invalid ({path}): {'; '.join(errors)}")
    return fields


def init_evaluate_state(path: Path, *, mode: str) -> None:
    """Initialize evaluate-state.md for a new evaluation round."""
    save_evaluate_state(
        path,
        build_initial_evaluate_state(mode=mode),
        merge=False,
    )


def evaluate_state_path(cycle_id: str, doc_round: int) -> Path:
    return doc_dir(cycle_id, doc_round) / "evaluate-state.md"


def resolve_evaluate_state_path_from_cycle(cycle_id: str, project_root: Path) -> Path:
    """Resolve revision{N}/evaluate-state.md via session-state.md active_doc."""
    active_doc = load_active_doc_from_cycle(cycle_id, project_root)
    return project_root / evaluate_state_path(cycle_id, active_doc)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="evaluate-state schema I/O")
    parser.add_argument("--schema", action="store_true", help="Print field schema JSON")
    parser.add_argument("--read", action="store_true", help="Read and validate file")
    parser.add_argument("--path", type=Path, help="Path to evaluate-state.md")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), ensure_ascii=False, indent=2))
        return 0

    if args.read:
        if not args.path:
            print("--read requires --path", file=sys.stderr)
            return 1
        print(json.dumps(load_evaluate_state(args.path.resolve()), ensure_ascii=False))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
