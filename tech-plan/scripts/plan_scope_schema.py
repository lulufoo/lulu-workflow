#!/usr/bin/env python3
"""Schema and I/O for tech-plan plan-scope-roles.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_VALID_SCOPES = frozenset({"topic", "feature"})


def default_roles_path() -> Path:
    return Path(__file__).resolve().parents[1] / "constraints" / "plan-scope-roles.json"


def load_roles(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"roles root must be an object: {path}")
    return data


def validate_roles(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append("version must be '1'")
    scopes = data.get("scopes")
    if not isinstance(scopes, dict):
        errors.append("scopes must be an object")
        return errors
    for scope in sorted(_VALID_SCOPES):
        if scope not in scopes:
            errors.append(f"missing scopes.{scope}")
            continue
        value = scopes[scope]
        if not isinstance(value, str) or not value.strip():
            errors.append(f"scopes.{scope}: missing or empty string")
    for key in scopes:
        if key not in _VALID_SCOPES:
            errors.append(f"unknown scope key: {key!r}")
    return errors


def get_scope_role(data: dict[str, Any], cycle_type: str) -> str:
    errors = validate_roles(data)
    if errors:
        raise ValueError(f"plan-scope-roles invalid: {'; '.join(errors)}")
    if cycle_type not in _VALID_SCOPES:
        raise ValueError(
            f"invalid cycle_type: {cycle_type!r} (allowed: {sorted(_VALID_SCOPES)})",
        )
    return str(data["scopes"][cycle_type]).strip()


def default_role_instances_path() -> Path:
    return Path(__file__).resolve().parents[1] / "constraints" / "instance" / "tech-role-instances.json"


def default_domain_instance_path() -> Path:
    return Path(__file__).resolve().parents[1] / "constraints" / "instance" / "tech-domain-instance.json"


def load_role_instances(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"role instances root must be an object: {path}")
    return data


def get_role_instance(data: dict[str, Any], cycle_type: str) -> dict[str, Any]:
    roles = data.get("roles", {})
    if cycle_type not in roles:
        raise KeyError(f"no role instance for cycle_type: {cycle_type!r}")
    return dict(roles[cycle_type])
