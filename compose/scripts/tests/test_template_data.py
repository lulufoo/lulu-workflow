#!/usr/bin/env python3
"""Test cache seeding helpers; framework templates load from lulu-workflow-framework SSOT."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

LEGACY_SECTION_REGISTRY: dict[str, Any] = {
    "version": "1",
    "section_order": ["NS", "NG", "I", "KD", "SK", "T"],
    "document_preamble": (
        "# {Feature Name} Tech Plan\n\n**Date:** YYYY-MM-DD\n**Version:** v1\n"
        "**Status:** Draft\n\n**Document References:**\n"
        "- Decision-doc: `{/<cycle_id>/lulu-approach/decision-doc.md}`\n"
        "- Product-doc: `{path}` / N/A\n\n---\n"
    ),
    "sections": {
        "NS": {
            "heading": "North Star",
            "aliases": ["north star"],
            "upstream": [],
            "relations": {},
            "desc": "One clear before→after outcome this change delivers. No exclusions, phases, or tasks.",
        },
        "NG": {
            "heading": "Non-Goals",
            "aliases": ["non-goals"],
            "upstream": ["NS"],
            "relations": {"NS": "operationalize"},
            "desc": "What this change will not do and what options are out of scope. No rationale essays or task lists.",
        },
        "I": {
            "heading": "Invariants",
            "aliases": ["invariants"],
            "upstream": ["NS", "NG"],
            "relations": {"NS": "operationalize", "NG": "respect_exclude"},
            "desc": "Constraints that must always hold after ship; each checkable. No option trade-offs or phase plans.",
        },
        "KD": {
            "heading": "Key Decisions",
            "aliases": ["key decisions"],
            "upstream": ["NS", "NG", "I"],
            "relations": {
                "NS": "operationalize",
                "NG": "respect_exclude",
                "I": "preserve_invariant",
            },
            "desc": "Chosen approach, why, and rejected alternatives; key open assumptions if any. No non-goals or task breakdown.",
        },
        "SK": {
            "heading": "Approach Skeleton",
            "aliases": ["approach skeleton"],
            "upstream": ["NS", "NG", "I", "KD"],
            "relations": {
                "NS": "operationalize",
                "NG": "respect_exclude",
                "I": "preserve_invariant",
                "KD": "instantiate",
            },
            "desc": "Phased execution skeleton: stages, Done per stage, dependencies, reversibility. No AC-level task list.",
        },
        "T": {
            "heading": "Tasks",
            "aliases": ["tasks"],
            "upstream": ["NS", "NG", "I", "KD", "SK"],
            "relations": {
                "NS": "operationalize",
                "NG": "respect_exclude",
                "I": "preserve_invariant",
                "KD": "instantiate",
                "SK": "decompose",
            },
            "desc": "Actionable, verifiable work items traceable to acceptance criteria. No north-star or direction rewrites.",
        },
    },
}

from framework_template_sources import (  # noqa: E402
    product_spec_inductive_scan_criteria,
    product_spec_section_form_registry,
    product_spec_section_registry,
    tech_arch_topic_domain_instance,
    tech_arch_topic_role_instance,
    tech_plan_feature_domain_instance,
    tech_plan_feature_role_instance,
    tech_plan_section_form_registry,
    tech_plan_section_registry,
)

TOPIC_ROLE_INSTANCE: dict[str, Any] = {
    "version": "1",
    "$schema_id": "role-schema",
    "cycle_type": "topic",
    "role_id": "system_architect",
    "role_prompt": (
        "You are acting as a **system architect**. Frame analysis from system boundaries, "
        "structural evolution, and long-term trade-offs."
    ),
    "cognitive_framework": "system boundaries, structural evolution, execution phasing at milestone granularity",
    "priority_tendency": "early registry sections establish the arc; SK and T carry phased momentum",
    "vocabulary_domain": [
        "module boundaries",
        "coupling",
        "evolution paths",
        "exclusion rationale",
        "system invariants",
        "phase Done criteria",
    ],
    "expressive_tendency": "boundary-explicit blocks first; phase skeleton with clear Done lines",
    "completion_bar": "direction clear, boundaries explicit, key decisions traceable",
}

TOPIC_DOMAIN_INSTANCE: dict[str, Any] = {
    "version": "1",
    "$schema_id": "domain-schema",
    "cycle_type": "topic",
    "domain_id": "tech_plan_topic",
    "cognitive_frame": "technical feasibility and design traceability",
    "information_nature": [
        "structural relationships between components",
        "process and data flows",
        "state transitions and lifecycle",
        "design decisions and their rationale",
        "constraints, invariants, and exclusions",
        "trade-off comparisons",
    ],
    "expression_conventions": "technical prose is analytical not narrative",
    "intent_anchor": "all content must be traceable to the decision-doc SSOT",
    "audience_type": "architects who validate structure and evolution",
}


def _workflow_scripts_dir() -> Path:
    from workflow_paths import WORKFLOW_SCRIPTS  # noqa: WPS433

    return WORKFLOW_SCRIPTS


def seed_template_cache(project_root: Path, section: str, key: str, payload: dict[str, Any]) -> None:
    """Write JSON template payload into project_root template cache."""
    scripts = _workflow_scripts_dir()
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from fetch_template import atomic_write, cache_path  # noqa: WPS433
    from subagent_config import detect_platform  # noqa: WPS433

    cache = cache_path(project_root.resolve(), detect_platform(), section, key)
    atomic_write(cache, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def seed_tech_plan_test_caches(project_root: Path) -> None:
    """Seed lulu-plan template caches for pytest from lulu-workflow-framework SSOT."""
    seed_template_cache(
        project_root,
        "lulu-plan",
        "tpt_section_registry_url",
        LEGACY_SECTION_REGISTRY,
    )
    seed_template_cache(
        project_root,
        "lulu-plan",
        "tpt_feature_role_instance_url",
        tech_plan_feature_role_instance(),
    )
    seed_template_cache(
        project_root,
        "lulu-plan",
        "tpt_feature_domain_instance_url",
        tech_plan_feature_domain_instance(),
    )
    seed_template_cache(
        project_root,
        "lulu-plan",
        "tpt_section_form_registry_url",
        tech_plan_section_form_registry(),
    )


def seed_tech_arch_test_caches(project_root: Path) -> None:
    """Seed lulu-arch topic role/domain caches for pytest from framework SSOT."""
    seed_template_cache(
        project_root,
        "lulu-arch",
        "tat_topic_role_instance_url",
        tech_arch_topic_role_instance(),
    )
    seed_template_cache(
        project_root,
        "lulu-arch",
        "tat_topic_domain_instance_url",
        tech_arch_topic_domain_instance(),
    )


def seed_product_spec_test_caches(project_root: Path) -> None:
    """Seed lulu-spec template caches for pytest from lulu-workflow-framework SSOT."""
    seed_template_cache(
        project_root,
        "lulu-spec",
        "pst_section_registry_url",
        product_spec_section_registry(),
    )
    seed_template_cache(
        project_root,
        "lulu-spec",
        "pst_section_form_registry_url",
        product_spec_section_form_registry(),
    )
    seed_template_cache(
        project_root,
        "lulu-spec",
        "pst_inductive_scan_criteria_url",
        product_spec_inductive_scan_criteria(),
    )


def legacy_section_registry_normalized() -> dict[str, Any]:
    from section_registry_schema import normalize_section_registry, validate_section_registry  # noqa: WPS433

    errors = validate_section_registry(LEGACY_SECTION_REGISTRY)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_section_registry(LEGACY_SECTION_REGISTRY)
