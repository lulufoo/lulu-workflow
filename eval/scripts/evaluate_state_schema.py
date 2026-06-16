#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for evaluate-state.md (v3).

CLI:
    python3 evaluate_state_schema.py --schema
    python3 evaluate_state_schema.py --validate --path <evaluate-state.md>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_SCHEMA: list[dict[str, Any]] = [
    {"field": "version", "type": "string", "required": True,
     "description": "Schema version (currently 3)"},
    {"field": "phase", "type": "string", "required": True,
     "description": "Fixed value: evaluate"},
    {"field": "eval_status", "type": "string", "required": True,
     "description": "Round-level status: active | done | abandoned"},
    {"field": "fix_phase", "type": "string", "required": True,
     "description": "probe | artifact-remediation | sot-remediation | done"},
    {"field": "corpus_ref", "type": "string", "required": False,
     "description": "EvalCorpus id@version (optional)"},
    {"field": "corpus_fingerprint", "type": "string", "required": False,
     "description": "Hash of composed dimension id set (dynamic corpus)"},
    {"field": "dimension_dispatch", "type": "string", "required": True,
     "description": "parallel | serial"},
    {"field": "dimension_status", "type": "string", "required": True,
     "description": "JSON map dim_id -> pending|in_progress|probed|complete"},
    {"field": "issue_counts", "type": "string", "required": True,
     "description": "JSON map dim_id -> {total, resolved}"},
    {"field": "total_issues", "type": "string", "required": True,
     "description": "Aggregate total issues"},
    {"field": "resolved_issues", "type": "string", "required": True,
     "description": "Aggregate resolved issues"},
    {"field": "fix_severity", "type": "string", "required": True,
     "description": "Highest severity from completed eval round summary"},
    {"field": "fix_severity_reason", "type": "string", "required": True,
     "description": "Fix severity reason"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s.get("required")}

_KEY_ORDER = [
    "version",
    "phase",
    "eval_status",
    "fix_phase",
    "corpus_ref",
    "corpus_fingerprint",
    "dimension_dispatch",
    "dimension_status",
    "issue_counts",
    "total_issues",
    "resolved_issues",
    "fix_severity",
    "fix_severity_reason",
]

_VALID_EVAL_STATUS = frozenset({"active", "done", "abandoned"})
_VALID_FIX_PHASE = frozenset({
    "probe",
    "artifact-remediation",
    "sot-remediation",
    "done",
})
_VALID_DIM_STATUS = frozenset({"pending", "in_progress", "probed", "complete"})
_VALID_DISPATCH = frozenset({"parallel", "serial"})
_DIM_STATUS_ORDER = {
    "pending": 0,
    "in_progress": 1,
    "probed": 2,
    "complete": 3,
}


def get_schema() -> list[dict[str, Any]]:
    """Return field definitions for evaluate-state.md v3."""
    return list(_SCHEMA)


def parse_frontmatter_fields(content: str) -> dict[str, str]:
    """Extract key: value pairs from YAML frontmatter."""
    fm_match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return {}
    result: dict[str, str] = {}
    for line in fm_match.group(1).splitlines():
        kv_match = re.match(r"^(\w+):\s*(.*)", line)
        if kv_match:
            result[kv_match.group(1)] = kv_match.group(2).strip()
    return result


def parse_json_map(raw: str, *, field_name: str) -> dict[str, Any]:
    """Parse a JSON object stored in frontmatter."""
    if not raw or raw.strip() == "":
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {field_name} JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return parsed


def serialize_json_map(data: dict[str, Any]) -> str:
    """Serialize map to compact JSON for frontmatter."""
    return json.dumps(data, separators=(",", ":"))


def parse_dimension_status(raw: str) -> dict[str, str]:
    """Parse dimension_status JSON string."""
    parsed = parse_json_map(raw, field_name="dimension_status")
    result: dict[str, str] = {}
    for key, value in parsed.items():
        status = str(value)
        if status not in _VALID_DIM_STATUS:
            raise ValueError(f"invalid dimension status for {key!r}: {status!r}")
        result[str(key)] = status
    return result


def parse_issue_counts(raw: str) -> dict[str, dict[str, str]]:
    """Parse issue_counts JSON string."""
    parsed = parse_json_map(raw, field_name="issue_counts")
    result: dict[str, dict[str, str]] = {}
    for dim_id, counts in parsed.items():
        if not isinstance(counts, dict):
            raise ValueError(f"issue_counts[{dim_id!r}] must be an object")
        total = counts.get("total")
        resolved = counts.get("resolved")
        if total is None or resolved is None:
            raise ValueError(f"issue_counts[{dim_id!r}] requires total and resolved")
        result[str(dim_id)] = {
            "total": str(total),
            "resolved": str(resolved),
        }
    return result


def build_initial_evaluate_state(
    *,
    dimension_ids: list[str],
    corpus_ref: str = "",
    corpus_fingerprint: str = "",
    dimension_dispatch: str = "parallel",
) -> dict[str, str]:
    """Return frontmatter fields for a new evaluate-state.md v3."""
    if not dimension_ids:
        raise ValueError("dimension_ids must be non-empty")
    if dimension_dispatch not in _VALID_DISPATCH:
        raise ValueError(
            f"invalid dimension_dispatch: {dimension_dispatch!r}",
        )

    dim_status = {dim_id: "pending" for dim_id in dimension_ids}
    issue_counts = {
        dim_id: {"total": "0", "resolved": "0"} for dim_id in dimension_ids
    }
    data: dict[str, str] = {
        "version": "3",
        "phase": "evaluate",
        "eval_status": "active",
        "fix_phase": "probe",
        "dimension_dispatch": dimension_dispatch,
        "dimension_status": serialize_json_map(dim_status),
        "issue_counts": serialize_json_map(issue_counts),
        "total_issues": "0",
        "resolved_issues": "0",
        "fix_severity": "",
        "fix_severity_reason": "",
    }
    if corpus_ref:
        data["corpus_ref"] = corpus_ref
    if corpus_fingerprint:
        data["corpus_fingerprint"] = corpus_fingerprint
    return data


def is_v3_state(data: dict[str, str]) -> bool:
    """Return True when evaluate-state uses v3 schema."""
    return data.get("version") == "3" and "dimension_status" in data


def validate_evaluate_state(data: dict[str, Any]) -> list[str]:
    """Return validation errors; empty list means valid."""
    errors: list[str] = []
    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")
    if data.get("version") not in (None, "3"):
        errors.append(f"invalid version: {data.get('version')!r} (expected '3')")
    if data.get("phase") not in (None, "evaluate"):
        errors.append(f"invalid phase: {data.get('phase')!r} (expected 'evaluate')")
    eval_status = data.get("eval_status", "")
    if eval_status and eval_status not in _VALID_EVAL_STATUS:
        errors.append(f"invalid eval_status: {eval_status!r}")
    fix_phase = data.get("fix_phase", "")
    if fix_phase and fix_phase not in _VALID_FIX_PHASE:
        errors.append(f"invalid fix_phase: {fix_phase!r}")
    dispatch = data.get("dimension_dispatch", "")
    if dispatch and dispatch not in _VALID_DISPATCH:
        errors.append(f"invalid dimension_dispatch: {dispatch!r}")
    raw_dim = data.get("dimension_status", "")
    if raw_dim:
        try:
            parse_dimension_status(raw_dim)
        except ValueError as exc:
            errors.append(str(exc))
    raw_counts = data.get("issue_counts", "")
    if raw_counts:
        try:
            parse_issue_counts(raw_counts)
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def _serialize_frontmatter(data: dict[str, str]) -> str:
    lines = ["---"]
    for key in _KEY_ORDER:
        if key in data:
            lines.append(f"{key}: {data[key]}")
    for key, value in data.items():
        if key not in _KEY_ORDER:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def save_evaluate_state(path: Path, data: dict[str, str], *, merge: bool = True) -> None:
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


def load_evaluate_state(path: Path) -> dict[str, str]:
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


def merge_dimension_status(
    data: dict[str, str],
    dim_id: str,
    status: str,
) -> dict[str, str]:
    """Patch one key in dimension_status; return updated frontmatter dict."""
    if status not in _VALID_DIM_STATUS:
        raise ValueError(f"invalid dimension status: {status!r}")
    dim_map = parse_dimension_status(data.get("dimension_status", "{}"))
    dim_map[dim_id] = status
    merged = dict(data)
    merged["dimension_status"] = serialize_json_map(dim_map)
    return merged


def patch_issue_count(
    data: dict[str, str],
    dim_id: str,
    *,
    total: str | None = None,
    resolved: str | None = None,
) -> dict[str, str]:
    """Update issue_counts entry for one dimension."""
    counts = parse_issue_counts(data.get("issue_counts", "{}"))
    entry = dict(counts.get(dim_id, {"total": "0", "resolved": "0"}))
    if total is not None:
        entry["total"] = str(total)
    if resolved is not None:
        entry["resolved"] = str(resolved)
    counts[dim_id] = entry
    merged = dict(data)
    merged["issue_counts"] = serialize_json_map(counts)
    return merged


def sum_issue_totals(data: dict[str, str], dispatch: list[str]) -> int:
    """Sum total issue counts for dispatch dimension ids."""
    counts = parse_issue_counts(data.get("issue_counts", "{}"))
    return sum(int(counts.get(dim, {}).get("total", "0") or "0") for dim in dispatch)


def all_dims_at_least(
    data: dict[str, str],
    dispatch: list[str],
    min_status: str,
) -> bool:
    """Return True when every dispatch dim is at or past min_status."""
    if min_status not in _VALID_DIM_STATUS:
        raise ValueError(f"invalid min_status: {min_status!r}")
    min_rank = _DIM_STATUS_ORDER[min_status]
    dim_map = parse_dimension_status(data.get("dimension_status", "{}"))
    for dim in dispatch:
        status = dim_map.get(dim, "pending")
        if _DIM_STATUS_ORDER.get(status, -1) < min_rank:
            return False
    return True


def _cli() -> int:
    parser = argparse.ArgumentParser(description="evaluate-state v3 schema I/O")
    parser.add_argument("--schema", action="store_true", help="Print field schema JSON")
    parser.add_argument("--validate", action="store_true", help="Validate file")
    parser.add_argument("--path", type=Path, help="Path to evaluate-state.md")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), ensure_ascii=False, indent=2))
        return 0

    if args.validate:
        if not args.path:
            print("--validate requires --path", file=sys.stderr)
            return 1
        try:
            fields = load_evaluate_state(args.path.resolve())
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps({"ok": True, "version": fields.get("version")}, ensure_ascii=False))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
