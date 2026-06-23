#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for compose stage workflow-state.md.

CLI:
    python3 workflow_state_schema.py --schema
    python3 workflow_state_schema.py --read  --path <workflow-state.md>
    python3 workflow_state_schema.py --read  --cycle-id <id> --project-root .
    python3 workflow_state_schema.py --write --path <workflow-state.md> --json '<object>'
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sys

_SCRIPTS = Path(__file__).resolve().parents[2]
_CORE = _SCRIPTS / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from delivered_refs_schema import serialize_delivered_refs  # noqa: E402
from session_state_schema import load_active_doc_from_cycle
from workflow_common import (
    parse_frontmatter_fields,
    read_md_field,
)
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID
from workflow_profile_paths import state_path

from transition_registry import session_states as _session_states  # noqa: E402

_SCHEMA: list[dict] = [
    {"field": "version", "type": "string", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "workflow", "type": "string", "required": True,
     "description": "Fixed value: tech-doc"},
    {"field": "mode", "type": "string", "required": True,
     "description": "Run mode: product | tech. Set by start.py on init; preserve unchanged on every manual write."},
    {"field": "cycle_type", "type": "string", "required": True,
     "description": "Cycle type: topic (architect role) | feature (technical expert role)"},
    {"field": "current_state", "type": "string", "required": True,
     "description": "Session state from transition-whitelist"},
    {"field": "evaluate_round", "type": "string", "required": True,
     "description": "Evaluation round counter (non-negative integer as string)"},
    {"field": "delivered_refs", "type": "string", "required": True,
     "description": "JSON array of {type, path} upstream delivered documents (start snapshot)"},
    {"field": "scope_refs", "type": "string", "required": False,
     "description": "JSON array; compose intent SSOT snapshot ([0]=primary; not used for Eval)"},
    {"field": "carry_forward_ref", "type": "string", "required": True,
     "description": "Absolute path to previous compose doc revision (may be empty)"},
    {"field": "updated_at", "type": "string", "required": True,
     "description": "ISO 8601 last-update timestamp"},
    {"field": "skip_evaluate_requested", "type": "string", "required": False,
     "description": "true only for Drafting -> ReadyForDelivery; omit on Delivered"},
    {"field": "historical", "type": "string", "required": False,
     "description": "Set to true when session is superseded by reopen"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}
_OPTIONAL_SCHEMA_FIELDS = {s["field"] for s in _SCHEMA if not s["required"]}
_SCHEMA_FIELD_NAMES = _REQUIRED_FIELDS | _OPTIONAL_SCHEMA_FIELDS

_REQUIRED_KEY_ORDER = [
    "version",
    "workflow",
    "mode",
    "cycle_type",
    "current_state",
    "evaluate_round",
    "delivered_refs",
    "scope_refs",
    "carry_forward_ref",
    "updated_at",
]

_VALID_MODES = frozenset({"product", "tech"})
_VALID_CYCLE_TYPES = frozenset({"topic", "feature"})
_SKIP_EVALUATE_VALUES = frozenset({"true", "false"})
_HISTORICAL_VALUES = frozenset({"true"})

def get_schema() -> list[dict]:
    """Return field definitions for workflow-state.md."""
    return list(_SCHEMA)


def _apply_schema_defaults(data: dict) -> dict:
    """Fill optional fields omitted by pre-migration workflow-state files."""
    return dict(data)


def validate_workflow_state(data: dict) -> list[str]:
    """Return list of validation error strings; empty means valid."""
    data = _apply_schema_defaults(data)
    errors: list[str] = []

    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")

    if data.get("version") not in (None, "1"):
        errors.append(f"invalid version: {data.get('version')!r} (expected '1')")

    if data.get("workflow") not in (None, "tech-doc"):
        errors.append(f"invalid workflow: {data.get('workflow')!r} (expected 'tech-doc')")

    mode = data.get("mode")
    if mode is not None and mode not in _VALID_MODES:
        errors.append(f"invalid mode: {mode!r} (allowed: {sorted(_VALID_MODES)})")

    cycle_type_val = data.get("cycle_type")
    if cycle_type_val is not None and cycle_type_val not in _VALID_CYCLE_TYPES:
        errors.append(
            f"invalid cycle_type: {cycle_type_val!r} "
            f"(allowed: {sorted(_VALID_CYCLE_TYPES)})"
        )

    current_state = data.get("current_state")
    if current_state is not None and current_state not in _session_states():
        errors.append(
            f"invalid current_state: {current_state!r} "
            f"(allowed: {sorted(_session_states())})"
        )

    evaluate_round = data.get("evaluate_round")
    if evaluate_round is not None:
        try:
            if int(evaluate_round) < 0:
                errors.append(f"invalid evaluate_round: {evaluate_round!r} (must be >= 0)")
        except (TypeError, ValueError):
            errors.append(f"invalid evaluate_round: {evaluate_round!r} (must be integer)")

    skip_eval = data.get("skip_evaluate_requested")
    if skip_eval is not None and skip_eval not in _SKIP_EVALUATE_VALUES:
        errors.append(
            f"invalid skip_evaluate_requested: {skip_eval!r} "
            f"(allowed: {sorted(_SKIP_EVALUATE_VALUES)} or omit)"
        )

    historical = data.get("historical")
    if historical is not None and historical not in _HISTORICAL_VALUES:
        errors.append(f"invalid historical: {historical!r} (allowed: 'true' or omit)")

    delivered_refs = data.get("delivered_refs")
    if delivered_refs is not None:
        try:
            from delivered_refs_schema import parse_delivered_refs

            parse_delivered_refs({"delivered_refs": delivered_refs})
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid delivered_refs: {exc}")

    scope_refs = data.get("scope_refs")
    if scope_refs is not None:
        try:
            from delivered_refs_schema import parse_scope_refs

            parse_scope_refs({"scope_refs": scope_refs})
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid scope_refs: {exc}")

    if data.get("current_state") == "Delivered" and "skip_evaluate_requested" in data:
        errors.append(
            "skip_evaluate_requested must be omitted when current_state is Delivered"
        )

    return errors


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

    payload = _apply_schema_defaults(dict(data))
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    errors = validate_workflow_state(payload)
    if errors:
        raise ValueError(f"workflow-state data invalid: {'; '.join(errors)}")

    path.write_text(_serialize_frontmatter(payload), encoding="utf-8")


def load_workflow_state(path: Path) -> dict:
    """Read and validate workflow-state.md; raise ValueError if missing or invalid."""
    if not path.exists():
        raise ValueError(f"workflow-state.md not found: {path}")
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        raise ValueError(f"missing YAML frontmatter in {path}")
    fields = _apply_schema_defaults(parse_frontmatter_fields(content))
    if not fields:
        raise ValueError(f"empty or invalid frontmatter in {path}")
    errors = validate_workflow_state(fields)
    if errors:
        raise ValueError(f"workflow-state.md invalid ({path}): {'; '.join(errors)}")
    return fields


def read_workflow_state(path: Path) -> Optional[dict]:
    """Read workflow-state.md without validation; None if absent or unreadable."""
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    fields = parse_frontmatter_fields(content)
    return fields or None


def read_current_state(path: Path, default: str = "Drafting") -> str:
    """Read current_state from workflow-state.md, returning default if absent."""
    fields = read_workflow_state(path)
    if not fields:
        return default
    state = fields.get("current_state", default)
    return state if state else default


def resolve_workflow_state_path_from_cycle(
    cycle_id: str,
    project_root: Path,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    """Resolve revision{N}/workflow-state.md via session-state.md active_doc."""
    active_doc = load_active_doc_from_cycle(cycle_id, project_root, profile_id=profile_id)
    return project_root / state_path(cycle_id, active_doc, profile_id)


def init_drafting(
    path: Path,
    *,
    mode: str,
    cycle_type: str = "feature",
    delivered_refs: list | None = None,
    scope_refs: list | None = None,
    carry_forward_ref: str = "",
    evaluate_round: int = 0,
) -> None:
    """Initialize workflow-state.md in Drafting state."""
    from delivered_refs_schema import DeliveredRef

    refs = delivered_refs or []
    normalized = [
        r if isinstance(r, DeliveredRef) else DeliveredRef(str(r["type"]), str(r["path"]))
        for r in refs
    ]
    scope = scope_refs or []
    normalized_scope = [
        r if isinstance(r, DeliveredRef) else DeliveredRef(str(r["type"]), str(r["path"]))
        for r in scope
    ]
    data = {
        "version": "1",
        "workflow": "tech-doc",
        "mode": mode,
        "cycle_type": cycle_type,
        "current_state": "Drafting",
        "evaluate_round": str(evaluate_round),
        "delivered_refs": serialize_delivered_refs(normalized),
        "carry_forward_ref": carry_forward_ref,
    }
    if normalized_scope:
        data["scope_refs"] = serialize_delivered_refs(normalized_scope)
    save_workflow_state(path, data, merge=False)


def mark_historical(path: Path) -> None:
    """Mark an existing workflow-state.md as historical (idempotent)."""
    if not path.exists():
        return
    fields = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
    if fields.get("historical") == "true":
        return
    save_workflow_state(path, {"historical": "true"}, merge=True)


def mark_invalidated(path: Path) -> None:
    """Set current_state to Invalidated, preserving all other fields."""
    if not path.exists():
        return
    fields = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
    if not fields:
        return
    save_workflow_state(path, {"current_state": "Invalidated"}, merge=True)


def _cli() -> int:
    parser = argparse.ArgumentParser(description="compose stage workflow-state.md schema utilities")
    parser.add_argument("--schema", action="store_true", help="Print JSON schema array and exit")
    parser.add_argument("--read", action="store_true", help="Print workflow state as JSON")
    parser.add_argument("--write", action="store_true", help="Write workflow state from --json")
    parser.add_argument("--path", type=Path, help="Path to workflow-state.md")
    parser.add_argument("--cycle-id", type=str, help="Cycle ID for --read")
    parser.add_argument("--project-root", type=Path, default=Path("."), help="Project root")
    parser.add_argument(
        "--profile",
        default=DEFAULT_COMPOSE_PROFILE_ID,
        help="Compose profile id (default: tech-plan)",
    )
    parser.add_argument("--json", type=str, help="JSON object for --write")
    args = parser.parse_args()
    profile_id = args.profile.strip() or DEFAULT_COMPOSE_PROFILE_ID

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    if args.read:
        if args.cycle_id:
            path = resolve_workflow_state_path_from_cycle(
                args.cycle_id.strip(),
                args.project_root.resolve(),
                profile_id=profile_id,
            )
        elif args.path:
            path = args.path
        else:
            parser.error("--read requires --path or --cycle-id")
        try:
            data = load_workflow_state(path)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return 0

    if args.write:
        if not args.path:
            parser.error("--write requires --path")
        if not args.json:
            parser.error("--write requires --json")
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

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(_cli())
