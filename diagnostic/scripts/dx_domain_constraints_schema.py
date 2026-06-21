#!/usr/bin/env python3
"""Schema and I/O for diagnostic domain-constraints.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dx_io import atomic_write_text

ALL_SECTION_KEYS: frozenset[str] = frozenset(
    {
        "user_prior",
        "problem",
        "direction",
        "decision_rationale",
        "scope",
        "assumptions",
        "execution_analysis",
    }
)

ALL_X_DIMENSIONS: tuple[str, ...] = (
    "acceptance_criteria",
    "impact_surface",
    "external_dependencies",
    "implementation_sketch",
    "gap_check",
)

_WORKFLOW_ROOT = Path(__file__).resolve().parents[2]

KERNEL_STAGE = "diagnostic"


def holder_constraints_path(project_root: Path, stage: str) -> Path | None:
    """Return `{stage}/constraints.json` under workflow root if present (holder SSOT)."""
    if stage == KERNEL_STAGE:
        return None
    rel = Path(stage) / "constraints.json"
    for candidate in (
        _WORKFLOW_ROOT / rel,
        project_root / "lulu-dev-workflow" / rel,
        project_root / rel,
    ):
        if candidate.is_file():
            return candidate
    return None


def _normalize_role(data: dict[str, Any]) -> dict[str, str] | None:
    role_raw = data.get("role")
    if isinstance(role_raw, dict):
        instruction = str(role_raw.get("instruction", "")).strip()
        if not instruction:
            return None
        persona = str(role_raw.get("persona", "")).strip()
        return {"persona": persona, "instruction": instruction}
    if isinstance(role_raw, str) and role_raw.strip():
        return {"persona": "", "instruction": role_raw.strip()}
    return None


def _default_constraints(*, stage: str) -> dict[str, Any]:
    return normalize_domain_constraints(
        {
            "version": "1",
            "stage": stage,
            "omitted_sections": [],
            "x_dimensions": list(ALL_X_DIMENSIONS),
        }
    )


def normalize_domain_constraints(data: dict[str, Any]) -> dict[str, Any]:
    omitted_raw = data.get("omitted_sections")
    omitted = omitted_raw if isinstance(omitted_raw, list) else []
    omitted_clean = [str(item) for item in omitted if str(item) in ALL_SECTION_KEYS]

    x_raw = data.get("x_dimensions")
    x_dims = x_raw if isinstance(x_raw, list) else list(ALL_X_DIMENSIONS)
    x_clean = [str(item) for item in x_dims if str(item) in ALL_X_DIMENSIONS]
    if not x_clean:
        x_clean = list(ALL_X_DIMENSIONS)

    normalized: dict[str, Any] = {
        "version": "1",
        "stage": str(data.get("stage", "")),
        "omitted_sections": omitted_clean,
        "x_dimensions": x_clean,
    }
    role = _normalize_role(data)
    if role:
        normalized["role"] = role
    return normalized


def validate_domain_constraints(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r}")
    for key in data.get("omitted_sections", []):
        if key not in ALL_SECTION_KEYS:
            errors.append(f"invalid omitted section: {key!r}")
    for dim in data.get("x_dimensions", []):
        if dim not in ALL_X_DIMENSIONS:
            errors.append(f"invalid x dimension: {dim!r}")
    role = data.get("role")
    if role is not None:
        if not isinstance(role, dict):
            errors.append("role must be an object")
        elif not str(role.get("instruction", "")).strip():
            errors.append("role.instruction is required when role is present")
    return errors


def load_domain_constraints(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"domain-constraints not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    normalized = normalize_domain_constraints(data)
    errors = validate_domain_constraints(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    return normalized


def save_domain_constraints(path: Path, data: dict[str, Any]) -> None:
    normalized = normalize_domain_constraints(data)
    errors = validate_domain_constraints(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(normalized, indent=2, ensure_ascii=False) + "\n")


def load_stage_defaults(project_root: Path, stage: str) -> dict[str, Any]:
    config_path = holder_constraints_path(project_root, stage)
    if config_path is None:
        return _default_constraints(stage=stage)
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return _default_constraints(stage=stage)
    merged = {k: v for k, v in payload.items() if k != "cache_subdir"}
    merged["stage"] = stage
    return normalize_domain_constraints(merged)


def holder_cache_subdir(project_root: Path, stage: str) -> str:
    """Session cache subdir from holder `constraints.json` (`cache_subdir`) or kernel default."""
    if stage == KERNEL_STAGE:
        return KERNEL_STAGE
    path = holder_constraints_path(project_root, stage)
    if path is None:
        return stage
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return stage
    subdir = str(payload.get("cache_subdir", "")).strip()
    return subdir if subdir else stage


def merge_domain_constraints(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    merged = normalize_domain_constraints(base)
    if "omitted_sections" in override:
        merged["omitted_sections"] = override["omitted_sections"]
    if "x_dimensions" in override:
        merged["x_dimensions"] = override["x_dimensions"]
    if "role" in override:
        merged["role"] = override["role"]
    return normalize_domain_constraints(merged)


def omitted_sections(constraints: dict[str, Any]) -> frozenset[str]:
    return frozenset(constraints.get("omitted_sections") or [])


def active_x_dimensions(constraints: dict[str, Any]) -> frozenset[str]:
    return frozenset(constraints.get("x_dimensions") or ALL_X_DIMENSIONS)


def is_section_active(constraints: dict[str, Any], section_key: str) -> bool:
    return section_key not in omitted_sections(constraints)


def is_x_dimension_active(constraints: dict[str, Any], dimension: str) -> bool:
    return dimension in active_x_dimensions(constraints)
