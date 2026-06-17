#!/usr/bin/env python3
"""Resolve tech-plan framework roles to config keys and fetch template markdown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from workflow_paths import WORKFLOW_SCRIPTS  # noqa: E402

if str(WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS))

from fetch_template import FetchTemplateError, fetch_template  # noqa: E402

SECTION = "tech-plan"

ROLE_KEYS: dict[str, str] = {
    "eval-ptc": "tpt_product_tech_spec_crosscheck_url",
    "feature-domain-instance": "tpt_feature_domain_instance_url",
    "feature-role-instance": "tpt_feature_role_instance_url",
    "intent-eval-framework": "tpt_intent_eval_framework_url",
    "outline-registry": "tpt_outline_registry_url",
    "section-kw-criteria": "tpt_section_kw_criteria_url",
    "section-registry": "tpt_section_registry_url",
}

_VALID_ROLES = frozenset(ROLE_KEYS)


class FetchPlanFrameworkError(Exception):
    """Raised when role resolution or template fetch fails."""


def resolve_key(role: str) -> str:
    if role not in _VALID_ROLES:
        raise FetchPlanFrameworkError(
            f"Invalid role {role!r}; expected one of: "
            f"{', '.join(sorted(_VALID_ROLES))}"
        )
    return ROLE_KEYS[role]


def fetch_plan_framework(
    role: str,
    project_root: Path,
    platform: Optional[str] = None,
    force: bool = False,
) -> str:
    key = resolve_key(role)
    try:
        return fetch_template(
            section=SECTION,
            key=key,
            project_root=project_root,
            platform=platform,
            force=force,
        )
    except FetchTemplateError as exc:
        raise FetchPlanFrameworkError(str(exc)) from exc


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch tech-plan framework template by role (markdown or JSON)",
    )
    parser.add_argument(
        "--role",
        required=True,
        choices=sorted(_VALID_ROLES),
        help="Framework role (eval-ptc, feature-domain-instance, feature-role-instance, intent-eval-framework, outline-registry, section-kw-criteria, section-registry)",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="Project root (default: current directory)",
    )
    parser.add_argument(
        "--platform",
        choices=["cursor", "copilot"],
        help="Platform cache namespace (default: auto-detect)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass cache and re-fetch from GitHub",
    )
    args = parser.parse_args(argv)

    try:
        content = fetch_plan_framework(
            role=args.role,
            project_root=Path(args.project_root).resolve(),
            platform=args.platform,
            force=args.force,
        )
    except FetchPlanFrameworkError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    sys.stdout.write(content)
    if not content.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
