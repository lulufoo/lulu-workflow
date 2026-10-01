"""Load compose templates from the SKILL install directory.

Library only: import ``load_compose_template`` or
``resolve_compose_template_path``. No agent CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent.parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()

from workflow_paths import WORKFLOW_ROOT, load_profile_json  # noqa: E402

from compose_template_registry import (  # noqa: E402
    ComposeTemplateError,
    resolve_template_ref,
)

_SKILL_PREFIX = "lulu-workflow/"


class ComposeTemplateLoadError(Exception):
    """Raised when a compose template cannot be loaded from the SKILL install."""


def _profile_id(*, profile_id: str | None, profile_path: Path | None) -> str:
    if profile_path is not None:
        pid = str(load_profile_json(profile_path).get("profile_id") or "").strip()
    else:
        pid = str(profile_id or "").strip()
    if not pid:
        raise ComposeTemplateLoadError("profile_id required")
    return pid


def resolve_compose_template_path(
    role: str,
    project_root: Path,
    *,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
    profile_path: Path | None = None,
) -> Path:
    path = Path(profile_path).resolve() if profile_path else None
    pid = _profile_id(profile_id=profile_id, profile_path=path)
    root = project_root.resolve()
    try:
        ref = resolve_template_ref(
            role,
            pid,
            project_root=root,
            cycle_id=cycle_id,
            conversation_id=conversation_id,
            profile_path=path,
        )
    except ComposeTemplateError as exc:
        raise ComposeTemplateLoadError(str(exc)) from exc
    if not ref.startswith(_SKILL_PREFIX):
        raise ComposeTemplateLoadError(
            f"compose template ref must start with {_SKILL_PREFIX!r} "
            f"(SKILL install); got {ref!r}"
        )
    resolved = (WORKFLOW_ROOT / ref[len(_SKILL_PREFIX) :]).resolve()
    if not resolved.is_file():
        raise ComposeTemplateLoadError(
            f"compose template missing from SKILL: {resolved}"
        )
    return resolved


def load_compose_template(
    role: str,
    project_root: Path,
    *,
    profile_id: str | None = None,
    cycle_id: str | None = None,
    conversation_id: str | None = None,
    profile_path: Path | None = None,
) -> str:
    path = resolve_compose_template_path(
        role,
        project_root,
        profile_id=profile_id,
        cycle_id=cycle_id,
        conversation_id=conversation_id,
        profile_path=profile_path,
    )
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise ComposeTemplateLoadError(f"compose template empty: {path}")
    return text
