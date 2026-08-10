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
        "direction_readiness",
        "direction",
        "settled_direction",
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


def _normalize_dimension_profile(raw: Any) -> dict[str, dict[str, str]]:
    """Canonical per-dimension ``{question, depth}`` map."""
    profile: dict[str, dict[str, str]] = {}
    if not isinstance(raw, dict):
        return profile
    for key, value in raw.items():
        dim = str(key)
        if dim not in ALL_X_DIMENSIONS or not isinstance(value, dict):
            continue
        entry: dict[str, str] = {}
        question = str(value.get("question", "")).strip()
        depth = str(value.get("depth", "")).strip()
        if question:
            entry["question"] = question
        if depth:
            entry["depth"] = depth
        if entry:
            profile[dim] = entry
    return profile


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
    profile = _normalize_dimension_profile(raw.get("dimension_profile"))
    if profile:
        result["dimension_profile"] = profile
    return result or None


def _normalize_context_docs(raw_docs: Any) -> dict[str, str]:
    """Normalize ``context.docs`` — flat map of self-describing key → path.

    Holder resolvers emit only loadable paths (omit missing). Decision stores
    the map verbatim; it does not resolve paths (archive-1.1 bind context map).
    """
    if not isinstance(raw_docs, dict):
        return {}
    docs: dict[str, str] = {}
    for key, value in raw_docs.items():
        name = str(key).strip()
        path = str(value).strip() if value is not None else ""
        if name and path:
            docs[name] = path
    return docs


def _normalize_context(data: dict[str, Any]) -> dict[str, Any] | None:
    raw = data.get("context")
    if not isinstance(raw, dict):
        return None
    # Replaced context.sources[] (upstream/topic); empty docs = nothing to load.
    return {"docs": _normalize_context_docs(raw.get("docs"))}


def context_docs_map(constraints: dict[str, Any]) -> dict[str, str]:
    """Return ``context.docs`` from normalized domain constraints (may be empty)."""
    context = constraints.get("context")
    if not isinstance(context, dict):
        return {}
    docs = context.get("docs")
    if not isinstance(docs, dict):
        return {}
    return {str(k): str(v) for k, v in docs.items() if str(k).strip() and str(v).strip()}


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
    # Nested approach sessions (P1.2 C): optional identity within stage=lulu-approach.
    node_id = str(data.get("node_id", "")).strip()
    if node_id:
        normalized["node_id"] = node_id
    session_role = str(data.get("session_role", "")).strip()
    if session_role:
        normalized["session_role"] = session_role
    role = _normalize_role(data)
    if role:
        normalized["role"] = role
    domain = _normalize_domain(data)
    if domain:
        normalized["domain"] = domain
    context = _normalize_context(data)
    if context:
        normalized["context"] = context
    reopen_authorization = str(data.get("reopen_authorization", "")).strip()
    if reopen_authorization:
        normalized["reopen_authorization"] = reopen_authorization
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
    context = data.get("context")
    if context is not None:
        if not isinstance(context, dict):
            errors.append("context must be an object")
        else:
            docs = context.get("docs")
            if docs is None:
                errors.append("context.docs is required when context is present")
            elif not isinstance(docs, dict):
                errors.append("context.docs must be an object")
            else:
                for key, value in docs.items():
                    if not str(key).strip():
                        errors.append("context.docs keys must be non-empty strings")
                    elif not isinstance(value, str) or not value.strip():
                        errors.append(
                            f"context.docs[{key!r}] must be a non-empty path string"
                        )
    domain = data.get("domain")
    if domain is not None:
        if not isinstance(domain, dict):
            errors.append("domain must be an object")
        else:
            if not isinstance(domain.get("name", ""), str):
                errors.append("domain.name must be a string")
            if not isinstance(domain.get("instruction", ""), str):
                errors.append("domain.instruction must be a string")
            profile = domain.get("dimension_profile")
            if profile is not None:
                if not isinstance(profile, dict):
                    errors.append("domain.dimension_profile must be an object")
                else:
                    for key, value in profile.items():
                        if key not in ALL_X_DIMENSIONS:
                            errors.append(f"invalid dimension_profile key: {key!r}")
                        elif not isinstance(value, dict):
                            errors.append(f"dimension_profile[{key!r}] must be an object")
                        else:
                            if not str(value.get("question", "")).strip():
                                errors.append(
                                    f"dimension_profile[{key!r}].question must be non-empty"
                                )
                            if not str(value.get("depth", "")).strip():
                                errors.append(
                                    f"dimension_profile[{key!r}].depth must be non-empty"
                                )
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


def load_constraints_config(path: Path) -> dict[str, Any]:
    """Load holder constraints file from explicit path (R1 contract)."""
    if not path.is_file():
        raise FileNotFoundError(f"constraints config not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"constraints config must be a JSON object: {path}")
    normalized = normalize_domain_constraints(data)
    errors = validate_domain_constraints(normalized)
    if errors:
        raise ValueError("; ".join(errors))
    return normalized


def resolve_stage(constraints_path: Path | None) -> str:
    """Return the stage declared by constraints, or the decision kernel stage."""
    if constraints_path is None:
        return KERNEL_STAGE
    return str(load_constraints_config(constraints_path)["stage"])


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
            base_profile = base_domain.get("dimension_profile")
            override_profile = override_domain.get("dimension_profile")
            if isinstance(base_profile, dict) and isinstance(override_profile, dict):
                merged_profile = {**base_profile}
                for dim, entry in override_profile.items():
                    if isinstance(entry, dict) and isinstance(merged_profile.get(dim), dict):
                        merged_profile[dim] = {**merged_profile[dim], **entry}
                    else:
                        merged_profile[dim] = entry
                merged_domain["dimension_profile"] = merged_profile
            merged["domain"] = merged_domain
        else:
            merged["domain"] = override_domain
    if "context" in override:
        # Whole-block replace: holder resolver hands already-resolved
        # ``context.docs`` map — decision never computes paths itself.
        merged["context"] = override["context"]
    if "node_id" in override:
        merged["node_id"] = override["node_id"]
    if "session_role" in override:
        merged["session_role"] = override["session_role"]
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


def domain_dimension_profile(constraints: dict[str, Any]) -> dict[str, dict[str, str]]:
    domain = constraints.get("domain")
    if isinstance(domain, dict) and isinstance(domain.get("dimension_profile"), dict):
        return {
            str(k): {str(kk): str(vv) for kk, vv in v.items()}
            for k, v in domain["dimension_profile"].items()
            if isinstance(v, dict)
        }
    return {}
