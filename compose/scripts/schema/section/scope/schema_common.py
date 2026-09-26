"""Shared path resolution and batch validation for plan-scope instance schemas."""

from __future__ import annotations

import sys
from pathlib import Path

_SCHEMA_DIR = Path(__file__).resolve().parent
_SCRIPTS = _SCHEMA_DIR.parents[3]
_KERNEL = _SCRIPTS / "_kernel"
_TEMPLATES = _SCRIPTS / "templates"
for _p in (_KERNEL, _TEMPLATES):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, WORKFLOW_SCRIPTS  # noqa: E402

VALID_CYCLE_TYPES = frozenset({"feature", "topic"})


def effective_project_root(project_root: Path | None) -> Path:
    return (project_root or Path.cwd()).resolve()


def resolve_fetched_instance_path(
    scheme_key: str,
    project_root: Path | None = None,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
    profile_path: Path | None = None,
) -> Path:
    """Return the SKILL install path for a compose scheme role."""
    root = effective_project_root(project_root)
    pid = profile_id or DEFAULT_COMPOSE_PROFILE_ID
    if str(WORKFLOW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(WORKFLOW_SCRIPTS))
    from compose_template_loader import resolve_compose_template_path  # noqa: WPS433

    return resolve_compose_template_path(
        scheme_key,
        root,
        profile_id=pid,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
        profile_path=profile_path,
    )


def validate_all_plan_scope_instances(project_root: Path | None = None) -> list[str]:
    from domain_instance_schema import validate_all_domain_instances  # noqa: WPS433
    from role_instance_schema import validate_all_role_instances  # noqa: WPS433

    return validate_all_role_instances(project_root) + validate_all_domain_instances(
        project_root,
    )
