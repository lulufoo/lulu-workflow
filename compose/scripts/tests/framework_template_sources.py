#!/usr/bin/env python3
"""Load compose stage templates shipped under this skill."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _skill_builtin_template(stage_dir: str, filename: str) -> dict[str, Any]:
    """Local skill builtin JSON under <workflow root>/<stage>/templates/."""
    path = Path(__file__).resolve().parents[3] / stage_dir / "templates" / filename
    if not path.is_file():
        raise FileNotFoundError(f"skill builtin template not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _skill_builtin_section_registry(stage_dir: str) -> dict[str, Any]:
    return _skill_builtin_template(stage_dir, "section-registry.json")


def _skill_builtin_section_form_registry(stage_dir: str) -> dict[str, Any]:
    return _skill_builtin_template(stage_dir, "section-form-registry.json")


def product_spec_section_registry() -> dict[str, Any]:
    return _skill_builtin_section_registry("lulu-spec")


def product_spec_section_form_registry() -> dict[str, Any]:
    return _skill_builtin_section_form_registry("lulu-spec")


def tech_design_section_registry() -> dict[str, Any]:
    return _skill_builtin_section_registry("lulu-design")


def tech_design_section_form_registry() -> dict[str, Any]:
    return _skill_builtin_section_form_registry("lulu-design")


def tech_plan_section_registry() -> dict[str, Any]:
    return _skill_builtin_section_registry("lulu-plan")


def tech_plan_section_form_registry() -> dict[str, Any]:
    return _skill_builtin_section_form_registry("lulu-plan")


def tech_plan_feature_role_instance() -> dict[str, Any]:
    return _skill_builtin_template("lulu-plan", "role-instance.json")


def tech_plan_feature_domain_instance() -> dict[str, Any]:
    return _skill_builtin_template("lulu-plan", "domain-instance.json")


def tech_design_feature_role_instance() -> dict[str, Any]:
    return _skill_builtin_template("lulu-design", "role-instance.json")


def tech_design_feature_domain_instance() -> dict[str, Any]:
    return _skill_builtin_template("lulu-design", "domain-instance.json")


def product_spec_feature_role_instance() -> dict[str, Any]:
    return _skill_builtin_template("lulu-spec", "role-instance.json")


def product_spec_feature_domain_instance() -> dict[str, Any]:
    return _skill_builtin_template("lulu-spec", "domain-instance.json")


def tech_arch_section_registry() -> dict[str, Any]:
    return _skill_builtin_section_registry("lulu-arch")


def tech_arch_topic_role_instance() -> dict[str, Any]:
    return _skill_builtin_template("lulu-arch", "role-instance.json")


def tech_arch_topic_domain_instance() -> dict[str, Any]:
    return _skill_builtin_template("lulu-arch", "domain-instance.json")


def product_blueprint_section_registry() -> dict[str, Any]:
    return _skill_builtin_section_registry("lulu-blueprint")


def product_blueprint_topic_role_instance() -> dict[str, Any]:
    return _skill_builtin_template("lulu-blueprint", "role-instance.json")


def product_blueprint_topic_domain_instance() -> dict[str, Any]:
    return _skill_builtin_template("lulu-blueprint", "domain-instance.json")


