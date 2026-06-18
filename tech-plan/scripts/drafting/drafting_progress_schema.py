#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for tech-plan drafting-progress.md.

CLI:
    python3 drafting_progress_schema.py --schema
    python3 drafting_progress_schema.py --read  --path <drafting-progress.md>
    python3 drafting_progress_schema.py --read  --cycle-id <id> --project-root .
    python3 drafting_progress_schema.py --write --path <drafting-progress.md> --json '<object>'
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts"
_CORE = _KERNEL_SCRIPTS / "core"
if str(_KERNEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_KERNEL_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from session_state_schema import load_active_doc_from_cycle
from workflow_common import parse_frontmatter_fields, read_md_field
from workflow_profile_paths import doc_dir

_SCHEMA: list[dict] = [
    {"field": "version", "type": "string", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "cycle_id", "type": "string", "required": True,
     "description": "Active cycle id"},
    {"field": "current_step", "type": "string", "required": True,
     "description": "Drafting sub-step: Ready | RoundIteration | FreeEdit"},
    {"field": "round", "type": "string", "required": False,
     "description": "Round counter; required when current_step is RoundIteration"},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}
_OPTIONAL_SCHEMA_FIELDS = {s["field"] for s in _SCHEMA if not s["required"]}
_SCHEMA_FIELD_NAMES = _REQUIRED_FIELDS | _OPTIONAL_SCHEMA_FIELDS

_REQUIRED_KEY_ORDER = [
    "version",
    "cycle_id",
    "current_step",
]

_VALID_STEPS = frozenset({"Ready", "RoundIteration", "FreeEdit"})


def get_schema() -> list[dict]:
    """Return field definitions for drafting-progress.md."""
    return list(_SCHEMA)


def validate_drafting_progress(data: dict) -> list[str]:
    """Return list of validation error strings; empty means valid."""
    errors: list[str] = []

    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")

    if data.get("version") not in (None, "1"):
        errors.append(f"invalid version: {data.get('version')!r} (expected '1')")

    current_step = data.get("current_step")
    if current_step is not None and current_step not in _VALID_STEPS:
        errors.append(
            f"invalid current_step: {current_step!r} "
            f"(allowed: {sorted(_VALID_STEPS)})"
        )

    cycle_id = data.get("cycle_id")
    if cycle_id is not None and not str(cycle_id).strip():
        errors.append("invalid cycle_id: must be non-empty")

    round_raw = data.get("round")
    if current_step == "RoundIteration":
        if round_raw is None or not str(round_raw).strip():
            errors.append("round is required when current_step is RoundIteration")
        else:
            try:
                if int(round_raw) < 1:
                    errors.append(f"invalid round: {round_raw!r} (must be >= 1)")
            except (TypeError, ValueError):
                errors.append(f"invalid round: {round_raw!r} (must be integer)")
    elif round_raw is not None and str(round_raw).strip():
        try:
            if int(round_raw) < 1:
                errors.append(f"invalid round: {round_raw!r} (must be >= 1)")
        except (TypeError, ValueError):
            errors.append(f"invalid round: {round_raw!r} (must be integer)")

    return errors


def _serialize_frontmatter(data: dict) -> str:
    lines = ["---"]
    for key in _REQUIRED_KEY_ORDER:
        if key in data:
            lines.append(f"{key}: {data[key]}")
    if "round" in data:
        lines.append(f"round: {data['round']}")
    for key in sorted(_OPTIONAL_SCHEMA_FIELDS - {"round"}):
        if key in data:
            lines.append(f"{key}: {data[key]}")
    for key, value in data.items():
        if key not in _SCHEMA_FIELD_NAMES:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def save_drafting_progress(path: Path, data: dict, *, merge: bool = True) -> None:
    """Write drafting-progress.md with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists() and merge:
        existing = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
        merged = dict(existing)
        merged.update(data)
        data = merged

    errors = validate_drafting_progress(data)
    if errors:
        raise ValueError(f"drafting-progress data invalid: {'; '.join(errors)}")

    path.write_text(_serialize_frontmatter(data), encoding="utf-8")


def load_drafting_progress(path: Path) -> dict:
    """Read and validate drafting-progress.md; raise ValueError if missing or invalid."""
    if not path.exists():
        raise ValueError(f"drafting-progress.md not found: {path}")
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        raise ValueError(f"missing YAML frontmatter in {path}")
    fields = parse_frontmatter_fields(content)
    if not fields:
        raise ValueError(f"empty or invalid frontmatter in {path}")
    errors = validate_drafting_progress(fields)
    if errors:
        raise ValueError(f"drafting-progress invalid: {'; '.join(errors)}")
    return fields


def read_current_step(path: Path, *, default: str | None = None) -> str | None:
    """Return current_step from drafting-progress.md, or default when absent."""
    if not path.exists():
        return default
    step = read_md_field(path, "current_step", default="")
    return step or default


def resolve_drafting_progress_path_from_cycle(cycle_id: str, project_root: Path) -> Path:
    """Resolve revision{N}/drafting-progress.md via session-state.md active_doc."""
    active_doc = load_active_doc_from_cycle(cycle_id, project_root, profile_id="tech-plan")
    return project_root / doc_dir(cycle_id, active_doc, "tech-plan") / "drafting-progress.md"


def _cli() -> int:
    parser = argparse.ArgumentParser(description="drafting-progress schema I/O")
    parser.add_argument("--schema", action="store_true", help="Print field schema JSON")
    parser.add_argument("--read", action="store_true", help="Read and validate file")
    parser.add_argument("--write", action="store_true", help="Write file from JSON")
    parser.add_argument("--path", type=Path, help="Path to drafting-progress.md")
    parser.add_argument("--cycle-id", help="Cycle id (with --project-root)")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--json", help="JSON object for --write")
    args = parser.parse_args()

    if args.schema:
        print(json.dumps(get_schema(), ensure_ascii=False, indent=2))
        return 0

    if args.read:
        if args.cycle_id:
            path = resolve_drafting_progress_path_from_cycle(
                args.cycle_id.strip(),
                args.project_root.resolve(),
            )
        elif args.path:
            path = args.path.resolve()
        else:
            print("provide --path or --cycle-id with --project-root", file=sys.stderr)
            return 1
        print(json.dumps(load_drafting_progress(path), ensure_ascii=False))
        return 0

    if args.write:
        if not args.path or not args.json:
            print("--write requires --path and --json", file=sys.stderr)
            return 1
        data = json.loads(args.json)
        save_drafting_progress(args.path.resolve(), data)
        print(json.dumps({"ok": True}, ensure_ascii=False))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
