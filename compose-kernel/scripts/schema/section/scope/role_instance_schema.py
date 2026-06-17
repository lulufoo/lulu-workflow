#!/usr/bin/env python3
"""Authoritative schema and I/O for tech-plan role instance JSON.

CLI:
    python3 role_instance_schema.py --schema
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from schema_common import VALID_CYCLE_TYPES, resolve_fetched_instance_path

SCHEMA_ID = "role-schema"
FEATURE_ROLE_KEY = "tpt_feature_role_instance_url"
TOPIC_ROLE_KEY = "tpt_topic_role_instance_url"

_SCHEMA: list[dict[str, Any]] = [
    {"field": "version", "type": "string", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "$schema_id", "type": "string", "required": True,
     "description": "Fixed value: role-schema"},
    {"field": "cycle_type", "type": "string", "required": True,
     "description": "topic (system architect) or feature (technical expert)"},
    {"field": "role_id", "type": "string", "required": True,
     "description": "Unique identifier for this role slice"},
    {"field": "role_prompt", "type": "string", "required": True,
     "description": "Natural-language persona and operational guidance for ### Role"},
    {"field": "cognitive_framework", "type": "string", "required": True,
     "description": "How this role frames problems — analysis dimensions"},
    {"field": "priority_tendency", "type": "string", "required": True,
     "description": "Which section types or content aspects this role prioritizes"},
    {"field": "vocabulary_domain", "type": "list[string]", "required": True,
     "description": "Vocabulary set characteristic of this role's reasoning"},
    {"field": "expressive_tendency", "type": "string", "required": True,
     "description": "Visual or structural style this role favors when communicating"},
    {"field": "completion_bar", "type": "string", "required": True,
     "description": "What 'done' means from this role's perspective"},
]

_ROLE_FIELD_KEYS = frozenset(
    entry["field"]
    for entry in _SCHEMA
    if entry["field"] not in {"version", "$schema_id", "cycle_type", "role_prompt"}
)

_FETCH_BINDINGS: dict[str, tuple[str, str]] = {
    "feature": (FEATURE_ROLE_KEY, "feature-role-instance"),
    "topic": (TOPIC_ROLE_KEY, "topic-role-instance"),
}


def get_schema() -> list[dict[str, Any]]:
    """Return field definitions for role instance JSON."""
    return list(_SCHEMA)


def role_instance_path(cycle_type: str, project_root: Path | None = None) -> Path:
    """Return path to role instance file for cycle_type."""
    key = cycle_type.strip().lower()
    if key not in _FETCH_BINDINGS:
        raise ValueError(
            f"invalid cycle_type: {cycle_type!r} (allowed: {sorted(VALID_CYCLE_TYPES)})",
        )
    config_key, fetch_role = _FETCH_BINDINGS[key]
    return resolve_fetched_instance_path(config_key, fetch_role, project_root)


def load_role_instance(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"role instance root must be an object: {path}")
    return data


def validate_role_instance(
    data: dict[str, Any],
    *,
    expected_cycle_type: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append("version must be '1'")
    if data.get("$schema_id") != SCHEMA_ID:
        errors.append(f"$schema_id must be {SCHEMA_ID!r}")

    cycle_type = data.get("cycle_type")
    if cycle_type not in VALID_CYCLE_TYPES:
        errors.append(f"cycle_type must be one of {sorted(VALID_CYCLE_TYPES)!r}")
    elif expected_cycle_type is not None and cycle_type != expected_cycle_type:
        errors.append(
            f"cycle_type mismatch: file has {cycle_type!r}, expected {expected_cycle_type!r}",
        )

    role_prompt = data.get("role_prompt")
    if not isinstance(role_prompt, str) or not role_prompt.strip():
        errors.append("role_prompt must be a non-empty string")

    for key in _ROLE_FIELD_KEYS:
        value = data.get(key)
        if key == "vocabulary_domain":
            if not isinstance(value, list) or not value:
                errors.append("vocabulary_domain must be a non-empty list")
            elif not all(isinstance(item, str) and item.strip() for item in value):
                errors.append("vocabulary_domain items must be non-empty strings")
            continue
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} must be a non-empty string")

    return errors


def get_role_prompt(data: dict[str, Any]) -> str:
    errors = validate_role_instance(data)
    if errors:
        raise ValueError(f"role instance invalid: {'; '.join(errors)}")
    return str(data["role_prompt"]).strip()


def get_role_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Return compose-facing role fields (### Role Fields), excluding role_prompt."""
    errors = validate_role_instance(data)
    if errors:
        raise ValueError(f"role instance invalid: {'; '.join(errors)}")
    return {key: data[key] for key in _ROLE_FIELD_KEYS}


def load_and_validate_role_instance(
    cycle_type: str,
    *,
    path: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    target = path or role_instance_path(cycle_type, project_root)
    if not target.exists():
        raise FileNotFoundError(f"role instance not found: {target}")
    data = load_role_instance(target)
    errors = validate_role_instance(data, expected_cycle_type=cycle_type)
    if errors:
        raise ValueError(f"{target.name} invalid: {'; '.join(errors)}")
    return data


def validate_all_role_instances(project_root: Path | None = None) -> list[str]:
    """Validate both topic and feature role instance files."""
    errors: list[str] = []
    for cycle_type in sorted(VALID_CYCLE_TYPES):
        try:
            path = role_instance_path(cycle_type, project_root)
            data = load_role_instance(path)
            errors.extend(
                f"{path.name}: {err}"
                for err in validate_role_instance(data, expected_cycle_type=cycle_type)
            )
        except (OSError, ValueError, FileNotFoundError) as exc:
            errors.append(f"role instance {cycle_type}: {exc}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tech-plan role instance schema")
    parser.add_argument("--schema", action="store_true", help="Print field schema JSON")
    args = parser.parse_args(argv)

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
