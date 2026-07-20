#!/usr/bin/env python3
"""Generic profile-aware drafting-progress.md schema and I/O helpers."""

from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path

_SCHEMA_SECTION = Path(__file__).resolve().parent
_SCRIPTS = _SCHEMA_SECTION.parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from session_state_schema import load_active_doc_from_cycle  # noqa: E402
from workflow_common import parse_frontmatter_fields, read_md_field  # noqa: E402
from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, load_profile  # noqa: E402
from workflow_profile_paths import doc_dir  # noqa: E402

_SCHEMA: list[dict] = [
    {"field": "version", "type": "string", "required": True},
    {"field": "cycle_id", "type": "string", "required": True},
    {"field": "current_step", "type": "string", "required": True},
]
_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}
_SCHEMA_FIELD_NAMES = {s["field"] for s in _SCHEMA}
_REQUIRED_KEY_ORDER = ["version", "cycle_id", "current_step"]
_STEP_INDUCTIVE = "Inductive"
_STEP_DEDUCTIVE = "Deductive"
_STEP_INITIALIZED = "Initialized"
_STEP_FREE_EDIT = "FreeEdit"
_LEGACY_STEP_READY = "Ready"


def normalize_step(step: str | None) -> str | None:
    """Map legacy drafting step names to the current profile-neutral names."""
    if step == _LEGACY_STEP_READY:
        return _STEP_INITIALIZED
    return step


def allowed_steps(
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    *,
    project_root: Path | None = None,
    cycle_id: str | None = None,
) -> frozenset[str]:
    """Return current_step values allowed by profile.drafting switches."""
    profile = load_profile(profile_id, project_root=project_root, cycle_id=cycle_id)
    drafting = profile.get("drafting") or {}
    steps = {_STEP_INITIALIZED}
    if drafting.get("inductive") is True:
        steps.add(_STEP_INDUCTIVE)
    else:
        # Non-inductive profiles use Deductive producer before Init.
        steps.add(_STEP_DEDUCTIVE)
    if drafting.get("freeedit") is True:
        steps.add(_STEP_FREE_EDIT)
    return frozenset(steps)


def validate_drafting_progress(
    data: dict,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    project_root: Path | None = None,
    cycle_id: str | None = None,
) -> list[str]:
    """Return validation errors; empty means valid."""
    errors: list[str] = []
    for field in _REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: '{field}'")
    if data.get("version") not in (None, "1"):
        errors.append(f"invalid version: {data.get('version')!r} (expected '1')")
    cycle_raw = data.get("cycle_id")
    if cycle_raw is not None and not str(cycle_raw).strip():
        errors.append("invalid cycle_id: must be non-empty")
    current_step = normalize_step(data.get("current_step"))
    steps = allowed_steps(profile_id, project_root=project_root, cycle_id=cycle_id)
    if current_step is not None and current_step not in steps:
        errors.append(
            f"invalid current_step: {current_step!r} (allowed: {sorted(steps)})",
        )
    return errors


def _serialize_frontmatter(data: dict) -> str:
    lines = ["---"]
    for key in _REQUIRED_KEY_ORDER:
        if key in data:
            lines.append(f"{key}: {data[key]}")
    for key, value in data.items():
        if key not in _SCHEMA_FIELD_NAMES:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def save_drafting_progress(
    path: Path,
    data: dict,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    project_root: Path | None = None,
    cycle_id: str | None = None,
    merge: bool = True,
) -> None:
    """Write drafting-progress.md with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and merge:
        existing = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
        merged = dict(existing)
        merged.update(data)
        data = merged
    errors = validate_drafting_progress(
        data,
        profile_id=profile_id,
        project_root=project_root,
        cycle_id=cycle_id,
    )
    if errors:
        raise ValueError(f"drafting-progress data invalid: {'; '.join(errors)}")
    path.write_text(_serialize_frontmatter(data), encoding="utf-8")


def load_drafting_progress(
    path: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
    project_root: Path | None = None,
    cycle_id: str | None = None,
) -> dict:
    """Read and validate drafting-progress.md."""
    if not path.exists():
        raise ValueError(f"drafting-progress.md not found: {path}")
    fields = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
    if "current_step" in fields:
        fields["current_step"] = normalize_step(fields.get("current_step"))
    if not fields:
        raise ValueError(f"empty or invalid frontmatter in {path}")
    errors = validate_drafting_progress(
        fields,
        profile_id=profile_id,
        project_root=project_root,
        cycle_id=cycle_id,
    )
    if errors:
        raise ValueError(f"drafting-progress invalid: {'; '.join(errors)}")
    return fields


def read_current_step(path: Path, *, default: str | None = None) -> str | None:
    """Return current_step from drafting-progress.md, or default when absent."""
    if not path.exists():
        return default
    step = normalize_step(read_md_field(path, "current_step", default=""))
    return step or default


def resolve_drafting_progress_path_from_cycle(
    cycle_id: str,
    project_root: Path,
    *,
    profile_id: str = DEFAULT_COMPOSE_PROFILE_ID,
) -> Path:
    """Resolve active revision drafting-progress.md for a profile."""
    active_doc = load_active_doc_from_cycle(cycle_id, project_root, profile_id=profile_id)
    return project_root / doc_dir(cycle_id, active_doc, profile_id, project_root) / "drafting-progress.md"


def _cli() -> int:
    parser = argparse.ArgumentParser(description="generic drafting-progress schema I/O")
    parser.add_argument("--schema", action="store_true", help="Print field schema JSON")
    args = parser.parse_args()
    if args.schema:
        print(json.dumps(_SCHEMA, ensure_ascii=False, indent=2))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
