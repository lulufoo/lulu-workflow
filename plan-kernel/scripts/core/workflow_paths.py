"""Path constants and profile loading for plan-kernel scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
EVAL_SCRIPTS = WORKFLOW_ROOT / "eval" / "scripts"
WORKFLOW_SCRIPTS = WORKFLOW_ROOT / "scripts"
PLAN_KERNEL_ROOT = WORKFLOW_ROOT / "plan-kernel"
CORE_SCRIPTS = PLAN_KERNEL_ROOT / "scripts" / "core"
SECTION_SCRIPTS = PLAN_KERNEL_ROOT / "scripts" / "section"
SCHEMA_SCRIPTS = PLAN_KERNEL_ROOT / "scripts" / "schema"
TECH_PLAN_SHELL = WORKFLOW_ROOT / "tech-plan"
TECH_PLAN_SCRIPTS = TECH_PLAN_SHELL / "scripts"
PROFILES_DIR = PLAN_KERNEL_ROOT / "profiles"

_DEFAULT_PROFILE_ID = "tech-plan"
_profile_cache: dict[str, dict[str, Any]] = {}


def load_profile(profile_id: str | None = None) -> dict[str, Any]:
    """Load and cache a profile JSON by id (default: tech-plan)."""
    pid = profile_id or _DEFAULT_PROFILE_ID
    if pid in _profile_cache:
        return _profile_cache[pid]
    path = PROFILES_DIR / f"{pid}.json"
    if not path.is_file():
        raise FileNotFoundError(f"profile not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    _profile_cache[pid] = data
    return data


def shell_path(profile: dict[str, Any], key: str) -> Path:
    """Resolve a shell_paths entry relative to WORKFLOW_ROOT."""
    shell_paths = profile.get("shell_paths") or {}
    rel = shell_paths.get(key)
    if not rel:
        raise KeyError(f"shell_paths.{key} missing in profile {profile.get('profile_id')!r}")
    return WORKFLOW_ROOT / rel
