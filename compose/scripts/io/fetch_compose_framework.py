"""Fetch compose framework templates by scheme role and profile mapping.

Library only: import ``fetch_compose_framework`` or
``resolve_compose_template_path``. No agent CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from workflow_paths import (  # noqa: E402
    WORKFLOW_SCRIPTS,
    load_profile_json,
)

if str(WORKFLOW_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(WORKFLOW_SCRIPTS))

from compose_template_registry import (  # noqa: E402
    ComposeTemplateError,
    framework_section,
    resolve_template_ref,
)
from fetch_template import (  # noqa: E402
    FetchTemplateError,
    cache_path,
    fetch_template,
    fetch_template_ref,
    is_direct_template_ref,
    resolve_template_ref_path,
    template_ref_file_name,
)
from subagent_config import detect_platform  # noqa: E402


class FetchComposeFrameworkError(Exception):
    """Raised when role resolution or template fetch fails."""


def fetch_compose_framework(
    role: str,
    project_root: Path,
    *,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
    platform: Optional[str] = None,
    force: bool = False,
    profile_path: Path | None = None,
) -> str:
    path = Path(profile_path).resolve() if profile_path else None
    if path is not None:
        pid = str(load_profile_json(path).get("profile_id") or "").strip()
    else:
        pid = str(profile_id or "").strip()
    if not pid:
        raise FetchComposeFrameworkError("profile_id required")
    root = project_root.resolve()
    try:
        section = framework_section(
            pid,
            project_root=root,
            cycle_id=cycle_id,
            conversation_id=conversation_id,
            profile_path=path,
        )
        template_ref = resolve_template_ref(
            role,
            pid,
            project_root=root,
            cycle_id=cycle_id,
            conversation_id=conversation_id,
            profile_path=path,
        )
        if is_direct_template_ref(template_ref):
            return fetch_template_ref(
                template_ref,
                root,
                stage=section,
                file_name=template_ref_file_name(template_ref, f"{role}.md"),
                platform=platform,
                force=force,
            )
        try:
            return fetch_template(
                section=section,
                key=template_ref,
                project_root=root,
                platform=platform,
                force=force,
            )
        except FetchTemplateError:
            legacy_cache = cache_path(
                root,
                detect_platform(platform),
                section,
                template_ref,
            )
            if legacy_cache.exists():
                cached = legacy_cache.read_text(encoding="utf-8")
                if cached.strip():
                    return cached
            raise
    except (ComposeTemplateError, FetchTemplateError) as exc:
        raise FetchComposeFrameworkError(str(exc)) from exc


def resolve_compose_template_path(
    role: str,
    project_root: Path,
    *,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
    platform: Optional[str] = None,
    force: bool = False,
    profile_path: Path | None = None,
) -> Path:
    """Return a direct source path or legacy/remote materialized cache path."""
    path = Path(profile_path).resolve() if profile_path else None
    if path is not None:
        pid = str(load_profile_json(path).get("profile_id") or "").strip()
    else:
        pid = str(profile_id or "").strip()
    if not pid:
        raise FetchComposeFrameworkError("profile_id required")

    root = project_root.resolve()
    try:
        section = framework_section(
            pid,
            project_root=root,
            cycle_id=cycle_id,
            conversation_id=conversation_id,
            profile_path=path,
        )
        template_ref = resolve_template_ref(
            role,
            pid,
            project_root=root,
            cycle_id=cycle_id,
            conversation_id=conversation_id,
            profile_path=path,
        )
        file_name = template_ref_file_name(template_ref, f"{role}.md")
        if is_direct_template_ref(template_ref):
            return resolve_template_ref_path(
                template_ref,
                root,
                stage=section,
                file_name=file_name,
                platform=platform,
                force=force,
            )

        cached = cache_path(
            root,
            detect_platform(platform),
            section,
            template_ref,
        )
        if not force and cached.exists() and cached.read_text(encoding="utf-8").strip():
            return cached
        fetch_compose_framework(
            role,
            root,
            profile_id=pid,
            cycle_id=cycle_id,
            conversation_id=conversation_id,
            platform=platform,
            force=force,
            profile_path=path,
        )
        if cached.exists() and cached.read_text(encoding="utf-8").strip():
            return cached
        raise FileNotFoundError(
            f"compose template cache not available after fetch: {cached}"
        )
    except (ComposeTemplateError, FetchTemplateError) as exc:
        raise FetchComposeFrameworkError(str(exc)) from exc
