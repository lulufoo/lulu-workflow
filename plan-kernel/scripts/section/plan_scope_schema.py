#!/usr/bin/env python3
"""Schema and I/O for tech-plan per-cycle_type role and domain instance JSON files."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_SECTION = Path(__file__).resolve().parent
_CORE = _SECTION.parent / "core"
sys.path.insert(0, str(_SECTION))
sys.path.insert(0, str(_CORE))
from workflow_paths import WORKFLOW_SCRIPTS, load_profile, shell_path  # noqa: E402

_PROFILE = load_profile("tech-plan")

_VALID_CYCLE_TYPES = frozenset({"topic", "feature"})


def default_instance_dir() -> Path:
    return shell_path(_PROFILE, "constraints_instance_dir")
_FETCH_SECTION = "tech-plan"
_FEATURE_ROLE_KEY = "tpt_feature_role_instance_url"
_FEATURE_DOMAIN_KEY = "tpt_feature_domain_instance_url"
_ROLE_FIELD_KEYS = frozenset(
    {
        "role_id",
        "cognitive_framework",
        "priority_tendency",
        "vocabulary_domain",
        "expressive_tendency",
        "completion_bar",
    }
)
_INSTANCE_FILENAMES: dict[str, str] = {
    "topic": "tech-plan-topic-role-instance.json",
    "feature": "tech-plan-feature-role-instance.json",
}
_DOMAIN_INSTANCE_FILENAMES: dict[str, str] = {
    "topic": "tech-plan-topic-domain-instance.json",
    "feature": "tech-plan-feature-domain-instance.json",
}
_DOMAIN_FIELD_KEYS = frozenset(
    {
        "domain_id",
        "cognitive_frame",
        "information_nature",
        "expression_conventions",
        "intent_anchor",
        "audience_type",
    }
)


def _effective_project_root(project_root: Path | None) -> Path:
    return (project_root or Path.cwd()).resolve()


def _resolve_fetched_instance_path(
    config_key: str,
    fetch_role: str,
    project_root: Path | None = None,
) -> Path:
    """Return template cache path for a feature instance; fetch when cache is empty."""
    root = _effective_project_root(project_root)
    if str(WORKFLOW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(WORKFLOW_SCRIPTS))
    from fetch_template import cache_path  # noqa: WPS433
    from subagent_config import detect_platform  # noqa: WPS433

    cached = cache_path(root, detect_platform(), _FETCH_SECTION, config_key)
    if cached.exists() and cached.read_text(encoding="utf-8").strip():
        return cached

    from fetch_plan_framework import fetch_plan_framework  # noqa: WPS433

    content = fetch_plan_framework(fetch_role, root)
    if not content.strip():
        raise FileNotFoundError(f"empty template for {fetch_role}")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    return cached


def role_instance_path(cycle_type: str, project_root: Path | None = None) -> Path:
    """Return path to role instance file for cycle_type."""
    key = cycle_type.strip().lower()
    if key not in _INSTANCE_FILENAMES:
        raise ValueError(
            f"invalid cycle_type: {cycle_type!r} (allowed: {sorted(_VALID_CYCLE_TYPES)})",
        )
    if key == "feature":
        return _resolve_fetched_instance_path(
            _FEATURE_ROLE_KEY,
            "feature-role-instance",
            project_root,
        )
    return default_instance_dir() / _INSTANCE_FILENAMES[key]


def domain_instance_path(cycle_type: str, project_root: Path | None = None) -> Path:
    """Return path to domain instance file for cycle_type."""
    key = cycle_type.strip().lower()
    if key not in _DOMAIN_INSTANCE_FILENAMES:
        raise ValueError(
            f"invalid cycle_type: {cycle_type!r} (allowed: {sorted(_VALID_CYCLE_TYPES)})",
        )
    if key == "feature":
        return _resolve_fetched_instance_path(
            _FEATURE_DOMAIN_KEY,
            "feature-domain-instance",
            project_root,
        )
    return default_instance_dir() / _DOMAIN_INSTANCE_FILENAMES[key]


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
    if data.get("$schema_id") != "domain-schema":
        errors.append("$schema_id must be 'domain-schema'")

    cycle_type = data.get("cycle_type")
    if cycle_type not in _VALID_CYCLE_TYPES:
        errors.append(f"cycle_type must be one of {sorted(_VALID_CYCLE_TYPES)!r}")
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


def validate_all_domain_instances(
    project_root: Path | None = None,
) -> list[str]:
    """Validate both topic and feature domain instance files."""
    errors: list[str] = []
    for cycle_type in sorted(_VALID_CYCLE_TYPES):
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


def validate_all_plan_scope_instances(project_root: Path | None = None) -> list[str]:
    return validate_all_role_instances(project_root) + validate_all_domain_instances(
        project_root,
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
    if data.get("$schema_id") != "role-schema":
        errors.append("$schema_id must be 'role-schema'")

    cycle_type = data.get("cycle_type")
    if cycle_type not in _VALID_CYCLE_TYPES:
        errors.append(f"cycle_type must be one of {sorted(_VALID_CYCLE_TYPES)!r}")
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
    fields: dict[str, Any] = {}
    for key in _ROLE_FIELD_KEYS:
        fields[key] = data[key]
    return fields


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
    for cycle_type in sorted(_VALID_CYCLE_TYPES):
        try:
            path = role_instance_path(cycle_type, project_root)
        except (OSError, ValueError, FileNotFoundError) as exc:
            errors.append(f"role instance {cycle_type}: {exc}")
            continue
        if cycle_type == "topic" and not path.exists():
            errors.append(f"missing role instance: {path}")
            continue
        try:
            data = load_role_instance(path)
            errors.extend(
                f"{path.name}: {err}"
                for err in validate_role_instance(data, expected_cycle_type=cycle_type)
            )
        except ValueError as exc:
            errors.append(str(exc))
    return errors
