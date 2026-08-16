#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for evaluate-state.md (v7).

CLI:
    python3 evaluate_state_schema.py --schema
    python3 evaluate_state_schema.py --validate --path <evaluate-state.md>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path
from typing import Any

_SCHEMA: list[dict[str, Any]] = [
    {"field": "version", "type": "string", "required": True,
     "description": "Schema version (currently 7)"},
    {"field": "phase", "type": "string", "required": True,
     "description": "Fixed value: evaluate"},
    {"field": "eval_status", "type": "string", "required": True,
     "description": "Round-level status: active | done | abandoned"},
    {"field": "eval_phase", "type": "string", "required": True,
     "description": "probe | remediation | done"},
    {"field": "eval_capability", "type": "string", "required": True,
     "description": "full-remediation | probe-only"},
    {"field": "corpus_ref", "type": "string", "required": False,
     "description": "EvalCorpus id@version (optional)"},
    {"field": "corpus_fingerprint", "type": "string", "required": False,
     "description": "Hash of composed dimension id set (dynamic corpus)"},
    {"field": "handling_policy", "type": "string", "required": True,
     "description": "JSON map dim_id -> class-default|human-first"},
    {"field": "dimension_dispatch", "type": "string", "required": True,
     "description": "parallel | serial"},
    {"field": "round_token", "type": "string", "required": True,
     "description": "Opaque token for this Eval round"},
    {"field": "dimension_status", "type": "string", "required": True,
     "description": "JSON map dim_id -> pending|probing|probed|remediating|complete"},
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
    {"field": "evaluate_round", "type": "string", "required": False,
     "description": "Per-L evaluation round M (optional; required for per-L layout)"},
    {"field": "focus_l", "type": "string", "required": False,
     "description": "Focus L id when using per-L evaluate layout"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s.get("required")}

_KEY_ORDER = [
    "version",
    "phase",
    "eval_status",
    "eval_phase",
    "eval_capability",
    "corpus_ref",
    "corpus_fingerprint",
    "handling_policy",
    "dimension_dispatch",
    "round_token",
    "dimension_status",
    "issue_counts",
    "total_issues",
    "resolved_issues",
    "fix_severity",
    "fix_severity_reason",
]

_VALID_EVAL_STATUS = frozenset({"active", "done", "abandoned"})
_VALID_EVAL_PHASE = frozenset({"probe", "remediation", "done"})
_VALID_EVAL_CAPABILITY = frozenset({"full-remediation", "probe-only"})
_VALID_HANDLING_POLICY = frozenset({"class-default", "human-first"})
_VALID_DIM_STATUS = frozenset({
    "pending",
    "probing",
    "probed",
    "remediating",
    "complete",
})
_VALID_DISPATCH = frozenset({"parallel", "serial"})
_DIM_STATUS_ORDER = {
    "pending": 0,
    "probing": 1,
    "probed": 2,
    "remediating": 3,
    "complete": 4,
}
_REMOVED_FIELDS = frozenset({
    "fix_phase",
    "force_human_resolution",
    "dimension_tokens",
})


def get_schema() -> list[dict[str, Any]]:
    """Return field definitions for evaluate-state.md v7."""
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


def parse_handling_policy(raw: str) -> dict[str, str]:
    """Parse the pinned per-Dimension handling policy map."""
    parsed = parse_json_map(raw, field_name="handling_policy")
    result: dict[str, str] = {}
    for key, value in parsed.items():
        if value not in _VALID_HANDLING_POLICY:
            raise ValueError(
                f"invalid handling_policy value for {key!r}: {value!r}",
            )
        result[str(key)] = str(value)
    return result


def parse_issue_counts(raw: str) -> dict[str, dict[str, int]]:
    """Parse issue_counts JSON string."""
    parsed = parse_json_map(raw, field_name="issue_counts")
    result: dict[str, dict[str, int]] = {}
    for dim_id, counts in parsed.items():
        if not isinstance(counts, dict):
            raise ValueError(f"issue_counts[{dim_id!r}] must be an object")
        if set(counts) != {"total", "resolved"}:
            raise ValueError(
                f"issue_counts[{dim_id!r}] requires exactly total and resolved",
            )
        total = counts.get("total")
        resolved = counts.get("resolved")
        if (
            isinstance(total, bool)
            or not isinstance(total, int)
            or total < 0
            or isinstance(resolved, bool)
            or not isinstance(resolved, int)
            or resolved < 0
        ):
            raise ValueError(
                f"issue_counts[{dim_id!r}] values must be nonnegative integers",
            )
        if resolved > total:
            raise ValueError(
                f"issue_counts[{dim_id!r}].resolved must not exceed total",
            )
        result[str(dim_id)] = {
            "total": total,
            "resolved": resolved,
        }
    return result


def build_initial_evaluate_state(
    *,
    dimension_ids: list[str],
    corpus_ref: str = "",
    corpus_fingerprint: str = "",
    dimension_dispatch: str = "parallel",
    evaluate_round: int | None = None,
    focus_l: str = "",
    round_token: str | None = None,
    eval_capability: str,
    handling_policy: dict[str, str],
) -> dict[str, str]:
    """Return frontmatter fields for a new evaluate-state.md v7."""
    if not dimension_ids:
        raise ValueError("dimension_ids must be non-empty")
    if dimension_dispatch not in _VALID_DISPATCH:
        raise ValueError(
            f"invalid dimension_dispatch: {dimension_dispatch!r}",
        )
    if eval_capability not in _VALID_EVAL_CAPABILITY:
        raise ValueError(f"invalid eval_capability: {eval_capability!r}")

    dim_status = {dim_id: "pending" for dim_id in dimension_ids}
    issue_counts = {
        dim_id: {"total": 0, "resolved": 0} for dim_id in dimension_ids
    }
    policy = dict(handling_policy)
    if set(policy) != set(dimension_ids):
        raise ValueError(
            "handling_policy keys must match dimension_ids",
        )
    if any(value not in _VALID_HANDLING_POLICY for value in policy.values()):
        raise ValueError("handling_policy values must be class-default or human-first")
    data: dict[str, str] = {
        "version": "7",
        "phase": "evaluate",
        "eval_status": "active",
        "eval_phase": "probe",
        "eval_capability": eval_capability,
        "dimension_dispatch": dimension_dispatch,
        "handling_policy": serialize_json_map(policy),
        "round_token": round_token or uuid.uuid4().hex,
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
    if evaluate_round is not None:
        data["evaluate_round"] = str(int(evaluate_round))
    if focus_l:
        data["focus_l"] = str(focus_l)
    return data


def is_v7_state(data: dict[str, str]) -> bool:
    """Return True only for a structurally recognizable v7 state."""
    return (
        data.get("version") == "7"
        and "dimension_status" in data
        and "handling_policy" in data
        and "eval_capability" in data
    )


def validate_evaluate_state(data: dict[str, Any]) -> list[str]:
    """Return validation errors; empty list means valid."""
    if data.get("version") != "7":
        return [
            "incompatible_round: evaluate-state version "
            f"{data.get('version')!r} is not supported (expected '7')",
        ]
    errors: list[str] = []
    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")
    for field in sorted(_REMOVED_FIELDS & data.keys()):
        errors.append(f"unsupported field: {field!r}")
    if data.get("phase") not in (None, "evaluate"):
        errors.append(f"invalid phase: {data.get('phase')!r} (expected 'evaluate')")
    eval_status = data.get("eval_status", "")
    if eval_status and eval_status not in _VALID_EVAL_STATUS:
        errors.append(f"invalid eval_status: {eval_status!r}")
    eval_phase = data.get("eval_phase", "")
    if eval_phase and eval_phase not in _VALID_EVAL_PHASE:
        errors.append(f"invalid eval_phase: {eval_phase!r}")
    capability = data.get("eval_capability", "")
    if capability and capability not in _VALID_EVAL_CAPABILITY:
        errors.append(f"invalid eval_capability: {capability!r}")
    dispatch = data.get("dimension_dispatch", "")
    if dispatch and dispatch not in _VALID_DISPATCH:
        errors.append(f"invalid dimension_dispatch: {dispatch!r}")
    if data.get("round_token") == "":
        errors.append("round_token must be a non-empty string")
    dimensions: dict[str, str] = {}
    raw_dim = data.get("dimension_status", "")
    try:
        dimensions = parse_dimension_status(raw_dim)
    except ValueError as exc:
        errors.append(str(exc))
    raw_policy = data.get("handling_policy", "")
    policy: dict[str, str] = {}
    try:
        policy = parse_handling_policy(raw_policy)
        if set(policy) != set(dimensions):
            errors.append(
                "handling_policy keys must match dimension_status keys",
            )
    except ValueError as exc:
        errors.append(str(exc))
    counts: dict[str, dict[str, int]] = {}
    raw_counts = data.get("issue_counts", "")
    try:
        counts = parse_issue_counts(raw_counts)
        if set(counts) != set(dimensions):
            errors.append("issue_counts keys must match dimension_status keys")
    except ValueError as exc:
        errors.append(str(exc))

    aggregates: dict[str, int] = {}
    for field in ("total_issues", "resolved_issues"):
        raw_value = data.get(field)
        try:
            value = int(raw_value)
            if str(value) != raw_value or value < 0:
                raise ValueError
            aggregates[field] = value
        except (TypeError, ValueError):
            errors.append(f"{field} must be a nonnegative integer")
    if counts and "total_issues" in aggregates:
        expected_total = sum(item["total"] for item in counts.values())
        if aggregates["total_issues"] != expected_total:
            errors.append(
                f"total_issues must equal issue_counts sum {expected_total}",
            )
    if counts and "resolved_issues" in aggregates:
        expected_resolved = sum(item["resolved"] for item in counts.values())
        if aggregates["resolved_issues"] != expected_resolved:
            errors.append(
                f"resolved_issues must equal issue_counts sum {expected_resolved}",
            )

    dimension_values = set(dimensions.values())
    if eval_status == "active" and eval_phase == "done":
        errors.append("inconsistent eval_status active with eval_phase done")
    if eval_status in {"done", "abandoned"} and eval_phase != "done":
        errors.append(
            f"inconsistent eval_status {eval_status} requires eval_phase done",
        )
    if eval_phase == "done" and eval_status not in {"done", "abandoned"}:
        errors.append("inconsistent eval_phase done requires terminal eval_status")
    if capability == "probe-only":
        if eval_phase == "remediation":
            errors.append("inconsistent probe-only capability with remediation phase")
        if eval_status == "abandoned":
            errors.append("inconsistent probe-only capability with abandoned status")

    if eval_phase == "probe" and not dimension_values <= {
        "pending",
        "probing",
        "probed",
        "complete",
    }:
        errors.append("inconsistent dimension_status for probe phase")
    if eval_phase == "remediation" and not dimension_values <= {
        "probed",
        "remediating",
        "complete",
    }:
        errors.append("inconsistent dimension_status for remediation phase")
    if eval_phase == "done" and eval_status == "done" and dimension_values != {
        "complete",
    }:
        errors.append("inconsistent done round requires all dimensions complete")
    if eval_phase == "done" and eval_status == "abandoned" and not dimension_values <= {
        "probed",
        "remediating",
        "complete",
    }:
        errors.append("inconsistent abandoned dimension_status")
    if (
        capability == "full-remediation"
        and eval_status == "done"
        and aggregates.get("resolved_issues") != aggregates.get("total_issues")
    ):
        errors.append("full-remediation done requires all issues resolved")
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
    if path.exists():
        existing = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
        if existing.get("version") != "7":
            raise ValueError(
                "incompatible_round: existing evaluate-state version "
                f"{existing.get('version')!r} is not supported (expected '7')",
            )
        if merge:
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
    entry = dict(counts.get(dim_id, {"total": 0, "resolved": 0}))
    if total is not None:
        entry["total"] = int(total)
    if resolved is not None:
        entry["resolved"] = int(resolved)
    counts[dim_id] = entry
    merged = dict(data)
    merged["issue_counts"] = serialize_json_map(counts)
    return merged


def sum_issue_totals(data: dict[str, str], dispatch: list[str]) -> int:
    """Sum total issue counts for dispatch dimension ids."""
    counts = parse_issue_counts(data.get("issue_counts", "{}"))
    return sum(counts.get(dim, {}).get("total", 0) for dim in dispatch)


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
    parser = argparse.ArgumentParser(description="evaluate-state v7 schema I/O")
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
