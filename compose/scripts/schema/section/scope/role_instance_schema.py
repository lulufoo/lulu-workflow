#!/usr/bin/env python3
"""Authoritative schema and I/O for compose stage role instance JSON.

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
ROLE_SCHEME_KEY = "role-instance"

_SCHEMA: list[dict[str, Any]] = [
    {"field": "version", "type": "string", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "$schema_id", "type": "string", "required": True,
     "description": "Fixed value: role-schema"},
    {"field": "cycle_type", "type": "string", "required": True,
     "description": "Container type label in instance payload (shell policy validates)"},
    {"field": "role_id", "type": "string", "required": True,
     "description": "Unique identifier for this role slice"},
    {"field": "role_prompt", "type": "string", "required": True,
     "description": "Natural-language persona and operational guidance (Role Instance)"},
    {"field": "cognitive_framework", "type": "string", "required": False,
     "description": (
         "Deprecated — genre cognitive frame lives on domain.cognitive_frame. "
         "If present, must be a non-empty string (legacy profiles)."
     )},
    {"field": "priority_tendency", "type": "string", "required": True,
     "description": "Which section types or content aspects this role prioritizes"},
    {"field": "vocabulary_domain", "type": "list[string]", "required": True,
     "description": "Vocabulary set characteristic of this role's reasoning"},
    {"field": "expressive_tendency", "type": "string", "required": True,
     "description": "Author stance and collaboration tone (not genre register/carriers)"},
    {"field": "completion_bar", "type": "string", "required": True,
     "description": "Author-side completion obligations (not signer/audience bar)"},
    {"field": "consume_policy", "type": "object", "required": False,
     "description": (
         "Optional intake consume policy: {rules:[{id,title?,when_true},…]}. "
         "Plan deductive Atomize requires non-empty rules (archive-6.0)."
     )},
]

_META_FIELDS = frozenset({"version", "$schema_id", "cycle_type", "role_prompt"})
_ROLE_FIELD_KEYS = frozenset(
    entry["field"] for entry in _SCHEMA if entry["field"] not in _META_FIELDS
)
_OPTIONAL_ROLE_FIELD_KEYS = frozenset(
    entry["field"]
    for entry in _SCHEMA
    if entry["field"] not in _META_FIELDS and not entry.get("required", True)
)


def get_schema() -> list[dict[str, Any]]:
    """Return field definitions for role instance JSON."""
    return list(_SCHEMA)


def role_instance_path(
    project_root: Path | None = None,
    profile_id: str | None = None,
) -> Path:
    """Return path to role instance template for the active compose profile."""
    return resolve_fetched_instance_path(
        ROLE_SCHEME_KEY,
        project_root,
        profile_id=profile_id,
    )


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
        optional = key in _OPTIONAL_ROLE_FIELD_KEYS
        if optional and value is None:
            continue
        if key == "vocabulary_domain":
            if not isinstance(value, list) or not value:
                errors.append("vocabulary_domain must be a non-empty list")
            elif not all(isinstance(item, str) and item.strip() for item in value):
                errors.append("vocabulary_domain items must be non-empty strings")
            continue
        if key == "consume_policy":
            if optional and key not in data:
                continue
            errors.extend(_validate_consume_policy(value))
            continue
        if optional and key not in data:
            continue
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} must be a non-empty string")

    return errors


def _validate_consume_policy(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["consume_policy must be an object when present"]
    rules = value.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("consume_policy.rules must be a non-empty array")
        return errors
    seen: set[str] = set()
    for index, rule in enumerate(rules):
        prefix = f"consume_policy.rules[{index}]"
        if not isinstance(rule, dict):
            errors.append(f"{prefix} must be an object")
            continue
        rid = rule.get("id")
        if not isinstance(rid, str) or not rid.strip():
            errors.append(f"{prefix}.id must be a non-empty string")
        else:
            key = rid.strip()
            if key in seen:
                errors.append(f"{prefix}.id duplicate: {key!r}")
            seen.add(key)
        when_true = rule.get("when_true")
        if not isinstance(when_true, str) or not when_true.strip():
            errors.append(f"{prefix}.when_true must be a non-empty string")
        title = rule.get("title")
        if title is not None and (
            not isinstance(title, str) or not title.strip()
        ):
            errors.append(f"{prefix}.title must be a non-empty string when present")
        extra = set(rule) - {"id", "title", "when_true"}
        if extra:
            errors.append(f"{prefix} unexpected fields {sorted(extra)}")
    extra_top = set(value) - {"rules"}
    if extra_top:
        errors.append(f"consume_policy unexpected fields {sorted(extra_top)}")
    return errors


def get_role_prompt(data: dict[str, Any]) -> str:
    errors = validate_role_instance(data)
    if errors:
        raise ValueError(f"role instance invalid: {'; '.join(errors)}")
    return str(data["role_prompt"]).strip()


def get_role_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Return non-prompt role fields (excludes role_prompt and meta keys)."""
    errors = validate_role_instance(data)
    if errors:
        raise ValueError(f"role instance invalid: {'; '.join(errors)}")
    out: dict[str, Any] = {}
    for key in _ROLE_FIELD_KEYS:
        if key in _OPTIONAL_ROLE_FIELD_KEYS and key not in data:
            continue
        out[key] = data[key]
    return out


def load_and_validate_role_instance(
    cycle_type: str,
    *,
    path: Path | None = None,
    project_root: Path | None = None,
    profile_id: str | None = None,
) -> dict[str, Any]:
    target = path or role_instance_path(project_root=project_root, profile_id=profile_id)
    if not target.exists():
        raise FileNotFoundError(f"role instance not found: {target}")
    data = load_role_instance(target)
    errors = validate_role_instance(data, expected_cycle_type=cycle_type)
    if errors:
        raise ValueError(f"{target.name} invalid: {'; '.join(errors)}")
    return data


def validate_all_role_instances(project_root: Path | None = None) -> list[str]:
    """Validate role instance template for the active compose profile."""
    errors: list[str] = []
    try:
        path = role_instance_path(project_root=project_root)
        data = load_role_instance(path)
        errors.extend(f"{path.name}: {err}" for err in validate_role_instance(data))
    except (OSError, ValueError, FileNotFoundError) as exc:
        errors.append(f"role instance: {exc}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compose stage role instance schema")
    parser.add_argument("--schema", action="store_true", help="Print field schema JSON")
    args = parser.parse_args(argv)

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
