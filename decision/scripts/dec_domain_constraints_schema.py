#!/usr/bin/env python3
"""Schema and I/O for decision domain-constraints.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dec_io import atomic_write_text

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

KERNEL_STAGE = "decision"


def default_cache_subdir(stage: str) -> str:
    return stage


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


def _normalize_domain(data: dict[str, Any]) -> dict[str, Any] | None:
    raw = data.get("domain")
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name", "")).strip()
    instruction = str(raw.get("instruction", "")).strip()
    if not name and not instruction:
        return None
    result: dict[str, Any] = {}
    if name:
        result["name"] = name
    if instruction:
        result["instruction"] = instruction
    framing_raw = raw.get("dimension_framing")
    if isinstance(framing_raw, dict):
        framing = {
            str(k): str(v).strip()
            for k, v in framing_raw.items()
            if str(k) in ALL_X_DIMENSIONS and str(v).strip()
        }
        if framing:
            result["dimension_framing"] = framing
    return result or None


def _normalize_context_loading(data: dict[str, Any]) -> dict[str, Any] | None:
    raw = data.get("context_loading")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    optional = bool(raw.get("optional", True))
    source_raw = raw.get("source")
    if not isinstance(source_raw, dict):
        return None
    subdir = str(source_raw.get("upstream_cache_subdir", "")).strip()
    doc_filename = str(source_raw.get("doc_filename", "")).strip()
    if not subdir or not doc_filename:
        return None
    source: dict[str, str] = {
        "upstream_cache_subdir": subdir,
        "doc_filename": doc_filename,
    }
    loaded_message = str(source_raw.get("loaded_message", "")).strip()
    if loaded_message:
        source["loaded_message"] = loaded_message
    return {"optional": optional, "source": source}


def default_kernel_constraints(*, stage: str) -> dict[str, Any]:
    return normalize_domain_constraints(
        {
            "version": "1",
            "stage": stage,
            "cache_subdir": default_cache_subdir(stage),
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

    stage = str(data.get("stage", "")).strip()
    cache_subdir = str(data.get("cache_subdir", "")).strip()
    if not cache_subdir and stage:
        cache_subdir = default_cache_subdir(stage)

    normalized: dict[str, Any] = {
        "version": "1",
        "stage": stage,
        "cache_subdir": cache_subdir,
        "omitted_sections": omitted_clean,
        "x_dimensions": x_clean,
    }
    objective = str(data.get("objective", "")).strip()
    if objective:
        normalized["objective"] = objective
    role = _normalize_role(data)
    if role:
        normalized["role"] = role
    domain = _normalize_domain(data)
    if domain:
        normalized["domain"] = domain
    context_loading = _normalize_context_loading(data)
    if context_loading:
        normalized["context_loading"] = context_loading
    return normalized


def validate_domain_constraints(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("version") != "1":
        errors.append(f"invalid version: {data.get('version')!r}")
    if not str(data.get("stage", "")).strip():
        errors.append("stage is required")
    if not str(data.get("cache_subdir", "")).strip():
        errors.append("cache_subdir is required")
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
    context_loading = data.get("context_loading")
    if context_loading is not None:
        if not isinstance(context_loading, dict):
            errors.append("context_loading must be an object")
        elif not isinstance(context_loading.get("source"), dict):
            errors.append("context_loading.source must be an object")
    domain = data.get("domain")
    if domain is not None:
        if not isinstance(domain, dict):
            errors.append("domain must be an object")
        else:
            if not isinstance(domain.get("name", ""), str):
                errors.append("domain.name must be a string")
            if not isinstance(domain.get("instruction", ""), str):
                errors.append("domain.instruction must be a string")
            framing = domain.get("dimension_framing")
            if framing is not None:
                if not isinstance(framing, dict):
                    errors.append("domain.dimension_framing must be an object")
                else:
                    for key, value in framing.items():
                        if key not in ALL_X_DIMENSIONS:
                            errors.append(f"invalid dimension_framing key: {key!r}")
                        elif not str(value).strip():
                            errors.append(f"dimension_framing[{key!r}] must be non-empty")
    stage = str(data.get("stage", "")).strip()
    if stage and stage != KERNEL_STAGE:
        if not str(data.get("objective", "")).strip():
            errors.append("objective is required for holder stages")
        if not isinstance(domain, dict):
            errors.append("domain is required for holder stages")
        elif domain is not None:
            if not str(domain.get("name", "")).strip():
                errors.append("domain.name is required for holder stages")
            if not str(domain.get("instruction", "")).strip():
                errors.append("domain.instruction is required for holder stages")
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


def load_constraints_config(path: Path, *, stage: str = "") -> dict[str, Any]:
    """Load holder constraints file from explicit path (R1 contract)."""
    if not path.is_file():
        raise FileNotFoundError(f"constraints config not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"constraints config must be a JSON object: {path}")
    if stage and not str(data.get("stage", "")).strip():
        data = {**data, "stage": stage}
    elif stage and str(data.get("stage", "")).strip() != stage:
        raise ValueError(
            f"constraints stage {data.get('stage')!r} does not match --stage {stage!r}",
        )
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
    if "objective" in override:
        merged["objective"] = override["objective"]
    if "domain" in override:
        base_domain = merged.get("domain")
        override_domain = override["domain"]
        if isinstance(base_domain, dict) and isinstance(override_domain, dict):
            merged_domain = {**base_domain, **override_domain}
            base_framing = base_domain.get("dimension_framing")
            override_framing = override_domain.get("dimension_framing")
            if isinstance(base_framing, dict) and isinstance(override_framing, dict):
                merged_domain["dimension_framing"] = {**base_framing, **override_framing}
            merged["domain"] = merged_domain
        else:
            merged["domain"] = override_domain
    return normalize_domain_constraints(merged)


def omitted_sections(constraints: dict[str, Any]) -> frozenset[str]:
    return frozenset(constraints.get("omitted_sections") or [])


def active_x_dimensions(constraints: dict[str, Any]) -> frozenset[str]:
    return frozenset(constraints.get("x_dimensions") or ALL_X_DIMENSIONS)


def is_section_active(constraints: dict[str, Any], section_key: str) -> bool:
    return section_key not in omitted_sections(constraints)


def is_x_dimension_active(constraints: dict[str, Any], dimension: str) -> bool:
    return dimension in active_x_dimensions(constraints)


def objective_text(constraints: dict[str, Any]) -> str:
    return str(constraints.get("objective", "")).strip()


def domain_instruction(constraints: dict[str, Any]) -> str:
    domain = constraints.get("domain")
    if isinstance(domain, dict):
        return str(domain.get("instruction", "")).strip()
    return ""


def domain_dimension_framing(constraints: dict[str, Any]) -> dict[str, str]:
    domain = constraints.get("domain")
    if isinstance(domain, dict) and isinstance(domain.get("dimension_framing"), dict):
        return {str(k): str(v) for k, v in domain["dimension_framing"].items()}
    return {}
