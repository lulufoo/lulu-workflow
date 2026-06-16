#!/usr/bin/env python3
"""Authoritative schema and I/O for tech-plan domain instance JSON.

CLI:
    python3 domain_instance_schema.py --schema
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from schema_common import (
    VALID_CYCLE_TYPES,
    default_instance_dir,
    resolve_fetched_instance_path,
)

SCHEMA_ID = "domain-schema"
FEATURE_DOMAIN_KEY = "tpt_feature_domain_instance_url"

_SCHEMA: list[dict[str, Any]] = [
    {"field": "version", "type": "string", "required": True,
     "description": "Schema version (currently 1)"},
    {"field": "$schema_id", "type": "string", "required": True,
     "description": "Fixed value: domain-schema"},
    {"field": "cycle_type", "type": "string", "required": True,
     "description": "topic (architecture plan) or feature (execution plan)"},
    {"field": "domain_id", "type": "string", "required": True,
     "description": "Unique identifier for this domain slice"},
    {"field": "cognitive_frame", "type": "string", "required": True,
     "description": "Analytical lens this domain uses to frame problems"},
    {"field": "information_nature", "type": "list[string]", "required": True,
     "description": "Characteristic information types this domain works with"},
    {"field": "expression_conventions", "type": "string", "required": True,
     "description": "Expressive norms and idiomatic forms for this domain"},
    {"field": "intent_anchor", "type": "string", "required": True,
     "description": "How this domain locks intent and prevents drift"},
    {"field": "audience_type", "type": "string", "required": True,
     "description": "Who consumes this document and what they need from it"},
]

_DOMAIN_FIELD_KEYS = frozenset(
    entry["field"]
    for entry in _SCHEMA
    if entry["field"] not in {"version", "$schema_id", "cycle_type"}
)

_INSTANCE_FILENAMES: dict[str, str] = {
    "topic": "tech-plan-topic-domain-instance.json",
    "feature": "tech-plan-feature-domain-instance.json",
}


def get_schema() -> list[dict[str, Any]]:
    """Return field definitions for domain instance JSON."""
    return list(_SCHEMA)


def domain_instance_path(cycle_type: str, project_root: Path | None = None) -> Path:
    """Return path to domain instance file for cycle_type."""
    key = cycle_type.strip().lower()
    if key not in _INSTANCE_FILENAMES:
        raise ValueError(
            f"invalid cycle_type: {cycle_type!r} (allowed: {sorted(VALID_CYCLE_TYPES)})",
        )
    if key == "feature":
        return resolve_fetched_instance_path(
            FEATURE_DOMAIN_KEY,
            "feature-domain-instance",
            project_root,
        )
    return default_instance_dir() / _INSTANCE_FILENAMES[key]


def load_domain_instance(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"domain instance root must be an object: {path}")
    return data


def validate_domain_instance(
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

    for key in _DOMAIN_FIELD_KEYS:
        value = data.get(key)
        if key == "information_nature":
            if not isinstance(value, list) or not value:
                errors.append("information_nature must be a non-empty list")
            elif not all(isinstance(item, str) and item.strip() for item in value):
                errors.append("information_nature items must be non-empty strings")
            continue
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} must be a non-empty string")

    return errors


def load_and_validate_domain_instance(
    cycle_type: str,
    *,
    path: Path | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    target = path or domain_instance_path(cycle_type, project_root)
    if not target.exists():
        raise FileNotFoundError(f"domain instance not found: {target}")
    data = load_domain_instance(target)
    errors = validate_domain_instance(data, expected_cycle_type=cycle_type)
    if errors:
        raise ValueError(f"{target.name} invalid: {'; '.join(errors)}")
    return data


def validate_all_domain_instances(project_root: Path | None = None) -> list[str]:
    """Validate both topic and feature domain instance files."""
    errors: list[str] = []
    for cycle_type in sorted(VALID_CYCLE_TYPES):
        try:
            path = domain_instance_path(cycle_type, project_root)
        except (OSError, ValueError, FileNotFoundError) as exc:
            errors.append(f"domain instance {cycle_type}: {exc}")
            continue
        if cycle_type == "topic" and not path.exists():
            errors.append(f"missing domain instance: {path}")
            continue
        try:
            data = load_domain_instance(path)
            errors.extend(
                f"{path.name}: {err}"
                for err in validate_domain_instance(data, expected_cycle_type=cycle_type)
            )
        except ValueError as exc:
            errors.append(str(exc))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tech-plan domain instance schema")
    parser.add_argument("--schema", action="store_true", help="Print field schema JSON")
    args = parser.parse_args(argv)

    if args.schema:
        print(json.dumps(get_schema(), indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
