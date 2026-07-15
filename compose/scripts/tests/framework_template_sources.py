#!/usr/bin/env python3
"""Load compose templates from lulu-workflow-framework (runtime SSOT).

Tests must not duplicate framework JSON under tests/fixtures.
Set LULU_WORKFLOW_FRAMEWORK_ROOT when the checkout is not at ~/Code/lulu-workflow-framework.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

_TEMPLATE_PREFIX = Path("lulu-dev-workflow") / "template"


def framework_repo_root() -> Path:
    env = os.environ.get("LULU_WORKFLOW_FRAMEWORK_ROOT", "").strip()
    if env:
        root = Path(env).expanduser().resolve()
        if root.is_dir():
            return root
        raise FileNotFoundError(
            f"LULU_WORKFLOW_FRAMEWORK_ROOT is not a directory: {root}",
        )
    sibling = Path(__file__).resolve().parents[4].parent / "lulu-workflow-framework"
    if sibling.is_dir():
        return sibling
    home_default = Path.home() / "Code" / "lulu-workflow-framework"
    if home_default.is_dir():
        return home_default
    raise FileNotFoundError(
        "lulu-workflow-framework checkout required for compose tests; "
        "clone it or set LULU_WORKFLOW_FRAMEWORK_ROOT",
    )


def framework_template_path(stage: str, filename: str) -> Path:
    return framework_repo_root() / _TEMPLATE_PREFIX / stage / filename


@lru_cache(maxsize=32)
def load_framework_json(stage: str, filename: str) -> dict[str, Any]:
    path = framework_template_path(stage, filename)
    if not path.is_file():
        raise FileNotFoundError(f"framework template not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def product_spec_section_registry() -> dict[str, Any]:
    return load_framework_json("spec", "20-product-spec-section-registry.json")


def product_spec_section_form_registry() -> dict[str, Any]:
    return load_framework_json("spec", "25-product-spec-section-form-registry.json")


def product_spec_outline_registry() -> dict[str, Any]:
    return load_framework_json("spec", "22-product-spec-feature-outline-registry.json")


def product_spec_inductive_scan_criteria() -> dict[str, Any]:
    return load_framework_json("spec", "27-product-spec-inductive-scan-criteria.json")


def tech_design_section_registry() -> dict[str, Any]:
    return load_framework_json("design", "42-tech-design-section-registry.json")


def tech_design_section_form_registry() -> dict[str, Any]:
    return load_framework_json("design", "49-tech-design-section-form-registry.json")


def tech_design_outline_registry() -> dict[str, Any]:
    return load_framework_json("design", "45-tech-design-feature-outline-registry.json")


def tech_plan_section_registry() -> dict[str, Any]:
    return load_framework_json("plan", "42-tech-plan-section-registry.json")


def tech_plan_section_form_registry() -> dict[str, Any]:
    return load_framework_json("plan", "49-tech-plan-section-form-registry.json")


def tech_plan_outline_registry() -> dict[str, Any]:
    return load_framework_json("plan", "45-tech-plan-feature-outline-registry.json")


def tech_plan_feature_role_instance() -> dict[str, Any]:
    return load_framework_json("plan", "46-tech-plan-feature-role-instance.json")


def tech_plan_feature_domain_instance() -> dict[str, Any]:
    return load_framework_json("plan", "47-tech-plan-feature-domain-instance.json")


def tech_arch_section_registry() -> dict[str, Any]:
    return load_framework_json("arch", "tech-arch-topic-section-registry.json")


def tech_arch_outline_registry() -> dict[str, Any]:
    return load_framework_json("arch", "tech-arch-topic-outline-registry.json")


def product_blueprint_section_registry() -> dict[str, Any]:
    return load_framework_json("blueprint", "product-blueprint-topic-section-registry.json")


def product_blueprint_outline_registry() -> dict[str, Any]:
    return load_framework_json("blueprint", "product-blueprint-topic-outline-registry.json")
