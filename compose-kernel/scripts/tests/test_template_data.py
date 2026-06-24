#!/usr/bin/env python3
"""Inline template payloads for tech-plan script tests (not runtime SSOT)."""

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
        "- Decision-doc: `{/<cycle_id>/tech/diagnostic/decision-doc.md}`\n"
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

OUTLINE_REGISTRY_FEATURE: dict[str, Any] = {
    "version": "1",
    "$schema_id": "outline-schema",
    "cycle_type": "feature",
    "outline_order": ["OV", "BD", "DS", "IV", "PL", "VF"],
    "blocks": {
        "OV": {
            "heading": "Overview",
            "intents": ["CTX", "GO"],
            "guidance": "One compact opening arc; CTX H3 before GO H3; no scope tables or architecture in this block.",
            "contract": {
                "required": ["Two H3 intents in narrative order (context before goal)"],
                "forbidden": ["Path inventories or scope tables (belongs in BD)"],
            },
        },
        "BD": {
            "heading": "Boundaries",
            "intents": ["SC", "NG"],
            "guidance": "Two H3 intents as scope box: surfaces in play, then exclusions; tables preferred over prose when enumerating.",
            "contract": {
                "required": ["H3 order: SC → NG"],
                "forbidden": ["Checkable invariants list (belongs in IV)"],
            },
        },
        "DS": {
            "heading": "Design",
            "intents": ["AR", "KD"],
            "guidance": "Two H3 intents: structure before decisions.",
            "contract": {
                "required": ["H3 order: AR → KD"],
                "forbidden": ["Task decomposition or checkbox steps (belongs in PL)"],
            },
        },
        "IV": {
            "heading": "Invariants",
            "intents": ["I"],
            "guidance": "Single I H3; checkable invariant list as primary carrier.",
            "contract": {
                "required": ["Checkable invariants as a list"],
                "forbidden": ["Phase tables or checkbox steps (belongs in PL)"],
            },
        },
        "PL": {
            "heading": "Implementation Plan",
            "intents": ["SK", "T"],
            "guidance": "Single execution thread: SK H3 before T H3.",
            "contract": {
                "required": ["SK opens with Execution arc lead-in before the phase table"],
                "forbidden": ["Prose-only task lists without checkbox steps"],
            },
        },
        "VF": {
            "heading": "Verification",
            "intents": ["VF"],
            "guidance": "Single VF H3; checklist or table as primary carrier.",
            "contract": {
                "required": ["AC-to-task-id traceability"],
                "forbidden": ["Implementation steps or execution instructions (belongs in PL)"],
            },
        },
    },
}

FEATURE_ROLE_INSTANCE: dict[str, Any] = {
    "version": "1",
    "$schema_id": "role-schema",
    "cycle_type": "feature",
    "role_id": "technical_expert",
    "role_prompt": "You are acting as a **technical expert** optimizing for execution momentum.",
    "cognitive_framework": "implementability, verifiability, rollback, next-step clarity",
    "priority_tendency": "SK and T sections first for execution momentum",
    "vocabulary_domain": ["file paths", "checkbox steps", "acceptance criteria"],
    "expressive_tendency": "bite-sized checkbox task blocks",
    "completion_bar": "next step is obvious",
}

FEATURE_DOMAIN_INSTANCE: dict[str, Any] = {
    "version": "1",
    "$schema_id": "domain-schema",
    "cycle_type": "feature",
    "domain_id": "tech_plan_feature",
    "cognitive_frame": "execution readiness grounded in design traceability",
    "information_nature": [
        "executable next steps and file touch points",
        "structural relationships between components",
        "verification commands and acceptance checks",
    ],
    "expression_conventions": "action-oriented narrative; checkbox steps when allowed",
    "intent_anchor": "decision-doc remains SSOT for scope and boundaries",
    "audience_type": "agent or engineer about to implement the next step",
}

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
    """Seed minimal tech-plan template caches for pytest (under project_root/.cache)."""
    seed_template_cache(
        project_root,
        "tech-plan",
        "tpt_section_registry_url",
        LEGACY_SECTION_REGISTRY,
    )
    seed_template_cache(
        project_root,
        "tech-plan",
        "tpt_feature_role_instance_url",
        FEATURE_ROLE_INSTANCE,
    )
    seed_template_cache(
        project_root,
        "tech-plan",
        "tpt_feature_domain_instance_url",
        FEATURE_DOMAIN_INSTANCE,
    )


def legacy_section_registry_normalized() -> dict[str, Any]:
    from section_registry_schema import normalize_section_registry, validate_section_registry  # noqa: WPS433

    errors = validate_section_registry(LEGACY_SECTION_REGISTRY)
    if errors:
        raise ValueError("; ".join(errors))
    return normalize_section_registry(LEGACY_SECTION_REGISTRY)
