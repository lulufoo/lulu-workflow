#!/usr/bin/env python3
"""Authoritative schema and I/O helpers for tech-design drafting-progress.md."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose-kernel" / "scripts"
if str(_KERNEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_KERNEL_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from session_state_schema import load_active_doc  # noqa: E402
from workflow_common import parse_frontmatter_fields, read_md_field  # noqa: E402
from workflow_profile_paths import doc_dir, session_state_path  # noqa: E402

PROFILE_ID = "tech-design"

_SCHEMA: list[dict] = [
    {"field": "version", "type": "string", "required": True},
    {"field": "cycle_id", "type": "string", "required": True},
    {"field": "current_step", "type": "string", "required": True},
    {"field": "round", "type": "string", "required": False},
]

_REQUIRED_FIELDS = {s["field"] for s in _SCHEMA if s["required"]}
_OPTIONAL_SCHEMA_FIELDS = {s["field"] for s in _SCHEMA if not s["required"]}
_SCHEMA_FIELD_NAMES = _REQUIRED_FIELDS | _OPTIONAL_SCHEMA_FIELDS
_REQUIRED_KEY_ORDER = ["version", "cycle_id", "current_step"]
_VALID_STEPS = frozenset({"Ready", "RoundIteration", "FreeEdit"})


def validate_drafting_progress(data: dict) -> list[str]:
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
            f"(allowed: {sorted(_VALID_STEPS)})",
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
            except ValueError:
                errors.append(f"invalid round: {round_raw!r} (must be integer)")
    elif round_raw is not None and str(round_raw).strip():
        try:
            if int(round_raw) < 1:
                errors.append(f"invalid round: {round_raw!r} (must be >= 1)")
        except ValueError:
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
    if not path.exists():
        raise ValueError(f"drafting-progress.md not found: {path}")
    fields = parse_frontmatter_fields(path.read_text(encoding="utf-8"))
    if not fields:
        raise ValueError(f"empty or invalid frontmatter in {path}")
    errors = validate_drafting_progress(fields)
    if errors:
        raise ValueError(f"drafting-progress invalid: {'; '.join(errors)}")
    return fields


def read_current_step(path: Path, *, default: str | None = None) -> str | None:
    if not path.exists():
        return default
    step = read_md_field(path, "current_step", default="")
    return step or default


def _active_doc(cycle_id: str, project_root: Path) -> int:
    return load_active_doc(
        project_root / session_state_path(cycle_id, PROFILE_ID, project_root),
        default=1,
    )


def resolve_drafting_progress_path_from_cycle(cycle_id: str, project_root: Path) -> Path:
    active_doc = _active_doc(cycle_id, project_root)
    return project_root / doc_dir(cycle_id, active_doc, PROFILE_ID, project_root) / "drafting-progress.md"
