"""Shared path resolution and batch validation for plan-scope instance schemas."""

from __future__ import annotations

import sys
from pathlib import Path

_SCHEMA_DIR = Path(__file__).resolve().parent
_SCRIPTS = _SCHEMA_DIR.parents[3]
_CORE = _SCRIPTS / "core"
_IO = _SCRIPTS / "io"
for _p in (_CORE, _IO):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from workflow_paths import DEFAULT_COMPOSE_PROFILE_ID, WORKFLOW_SCRIPTS  # noqa: E402

VALID_CYCLE_TYPES = frozenset({"feature"})


def effective_project_root(project_root: Path | None) -> Path:
    return (project_root or Path.cwd()).resolve()


def resolve_fetched_instance_path(
    scheme_key: str,
    project_root: Path | None = None,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
) -> Path:
    """Return template cache path for a compose scheme role; fetch when cache is empty."""
    root = effective_project_root(project_root)
    pid = profile_id or DEFAULT_COMPOSE_PROFILE_ID
    if str(WORKFLOW_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(WORKFLOW_SCRIPTS))
    from compose_template_registry import framework_section, resolve_config_key  # noqa: WPS433
    from fetch_template import cache_path  # noqa: WPS433
    from subagent_config import detect_platform  # noqa: WPS433

    section = framework_section(
        pid,
        project_root=root,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
    )
    config_key = resolve_config_key(
        scheme_key,
        pid,
        project_root=root,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
    )
    cached = cache_path(root, detect_platform(), section, config_key)
    if cached.exists() and cached.read_text(encoding="utf-8").strip():
        return cached

    from fetch_compose_framework import fetch_compose_framework  # noqa: WPS433

    content = fetch_compose_framework(
        scheme_key,
        root,
        profile_id=pid,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
    )
    if not content.strip():
        raise FileNotFoundError(f"empty template for {scheme_key}")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(content if content.endswith("\n") else content + "\n", encoding="utf-8")
    return cached


def validate_all_plan_scope_instances(project_root: Path | None = None) -> list[str]:
    from domain_instance_schema import validate_all_domain_instances  # noqa: WPS433
    from role_instance_schema import validate_all_role_instances  # noqa: WPS433

    return validate_all_role_instances(project_root) + validate_all_domain_instances(
        project_root,
    )
