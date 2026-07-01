"""Compose template scheme and profile framework_templates resolution."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from workflow_paths import (  # noqa: E402
    DEFAULT_COMPOSE_PROFILE_ID,
    KERNEL_SCHEMES,
    load_profile,
)

_SCHEME_PATH = KERNEL_SCHEMES / "compose-template-scheme.json"
_scheme_cache: Optional[dict[str, Any]] = None


class ComposeTemplateError(Exception):
    """Raised when scheme or profile template resolution fails."""


def load_compose_template_scheme() -> dict[str, Any]:
    global _scheme_cache
    if _scheme_cache is None:
        _scheme_cache = json.loads(_SCHEME_PATH.read_text(encoding="utf-8"))
    return _scheme_cache


def scheme_template_keys() -> frozenset[str]:
    scheme = load_compose_template_scheme()
    keys: set[str] = set()
    for entry in scheme.get("templates", []):
        key = entry.get("key")
        if key:
            keys.add(str(key))
    return frozenset(keys)


def framework_section(
    profile_id: str | None = None,
    *,
    project_root: Path | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    profile = load_profile(
        profile_id or DEFAULT_COMPOSE_PROFILE_ID,
        project_root=project_root,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
    )
    section = profile.get("framework_section")
    if not section:
        raise ComposeTemplateError(
            f"framework_section missing in profile {profile.get('profile_id')!r}",
        )
    return str(section)


def resolve_config_key(
    scheme_key: str,
    profile_id: str | None = None,
    *,
    project_root: Path | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
) -> str:
    if scheme_key not in scheme_template_keys():
        raise ComposeTemplateError(
            f"Invalid compose template role {scheme_key!r}; "
            f"expected one of: {', '.join(sorted(scheme_template_keys()))}",
        )
    profile = load_profile(
        profile_id or DEFAULT_COMPOSE_PROFILE_ID,
        project_root=project_root,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
    )
    templates = profile.get("framework_templates") or {}
    config_key = templates.get(scheme_key)
    if not config_key:
        raise ComposeTemplateError(
            f"missing framework_templates[{scheme_key!r}] "
            f"in profile {profile.get('profile_id')!r}",
        )
    return str(config_key)
