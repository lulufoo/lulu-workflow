#!/usr/bin/env python3
"""Schema and I/O for hook-config.json (rwGuard)."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Optional

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
SKILL_ROOT = SCRIPTS_DIR.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from platforms.paths import platform_skills_root  # noqa: E402
from workflow_config_schema import detect_platform, read_platform_config  # noqa: E402

_DEFAULT_HOOK_CONFIG_PATH = "skill-config/lulu-dev-workflow/hook-config.json"

_DEFAULT_HOOK_CONFIG: dict[str, Any] = {
    "version": 1,
    "rwGuard": {
        "enable": True,
        "bypassWriteWhenDelivered": True,
        "defaults": {
            "readDirs": [".", "{platform-skills}"],
            "writeDirs": [".cache/{platform}/lulu-dev-workflow"],
        },
        "stages": {
            "tech-code": {
                "readDirs": [".", "{platform-skills}"],
                "writeDirs": ["."],
            },
        },
    },
}


def default_hook_config() -> dict[str, Any]:
    """Return a deep copy of the built-in default hook-config payload."""
    return copy.deepcopy(_DEFAULT_HOOK_CONFIG)


def resolve_hook_config_path(
    project_root: Path,
    platform: Optional[str] = None,
) -> Path:
    """Return path to hook-config.json via platform config pointer."""
    platform_cfg = read_platform_config(project_root, platform)
    hook_config_rel = platform_cfg.get("hookConfig", _DEFAULT_HOOK_CONFIG_PATH)
    return project_root / hook_config_rel


def validate_hook_config(data: object) -> list[str]:
    """Return validation error messages; empty list means valid."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root must be a JSON object"]
    version = data.get("version")
    if version != 1:
        errors.append("version must be 1")
    rw_guard = data.get("rwGuard")
    if not isinstance(rw_guard, dict):
        errors.append("rwGuard must be an object")
        return errors

    for key in ("enable", "bypassWriteWhenDelivered"):
        value = rw_guard.get(key)
        if value is not None and not isinstance(value, bool):
            errors.append(f"rwGuard.{key} must be a boolean")

    defaults = rw_guard.get("defaults")
    if defaults is not None:
        if not isinstance(defaults, dict):
            errors.append("rwGuard.defaults must be an object")
        else:
            errors.extend(_validate_dir_list(defaults.get("readDirs"), "rwGuard.defaults.readDirs"))
            errors.extend(_validate_dir_list(defaults.get("writeDirs"), "rwGuard.defaults.writeDirs"))

    stages = rw_guard.get("stages")
    if stages is not None:
        if not isinstance(stages, dict):
            errors.append("rwGuard.stages must be an object")
        else:
            for stage, stage_cfg in stages.items():
                if not isinstance(stage_cfg, dict):
                    errors.append(f"rwGuard.stages.{stage} must be an object")
                    continue
                prefix = f"rwGuard.stages.{stage}"
                enable = stage_cfg.get("enable")
                if enable is not None and not isinstance(enable, bool):
                    errors.append(f"{prefix}.enable must be a boolean")
                errors.extend(_validate_dir_list(stage_cfg.get("readDirs"), f"{prefix}.readDirs"))
                errors.extend(_validate_dir_list(stage_cfg.get("writeDirs"), f"{prefix}.writeDirs"))
    return errors


def _validate_dir_list(value: object, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return [f"{field} must be an array of strings"]
    return []


def load_hook_config(
    project_root: Path,
    platform: Optional[str] = None,
) -> dict[str, Any]:
    """Load hook-config.json; missing or invalid file falls back to built-in default."""
    target = resolve_hook_config_path(project_root, platform)
    if not target.exists():
        return default_hook_config()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default_hook_config()
    if validate_hook_config(data):
        return default_hook_config()
    return data


def ensure_hook_config(
    project_root: Path,
    platform: Optional[str] = None,
) -> tuple[Path, bool]:
    """Write default hook-config.json when missing. Returns (path, created)."""
    target = resolve_hook_config_path(project_root, platform)
    if target.exists():
        return target, False
    payload = default_hook_config()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target, True


def expand_path_template(path: str, platform: Optional[str] = None) -> str:
    """Expand supported placeholders in a configured directory template."""
    plat = detect_platform(platform)
    return (
        path
        .replace("{platform}", plat)
        .replace("{platform-skills}", platform_skills_root(plat).as_posix())
    )


def resolve_rw_guard(
    project_root: Path,
    stage: str,
    platform: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve effective rwGuard settings for a stage."""
    config = load_hook_config(project_root, platform)
    rw_guard = config.get("rwGuard") or {}
    plat = detect_platform(platform)

    global_enable = rw_guard.get("enable", True)
    bypass = rw_guard.get("bypassWriteWhenDelivered", True)
    defaults = rw_guard.get("defaults") or {}
    stage_cfg = (rw_guard.get("stages") or {}).get(stage) or {}

    stage_enable = stage_cfg.get("enable", global_enable)
    read_dirs = stage_cfg.get("readDirs", defaults.get("readDirs", ["."]))
    write_dirs = stage_cfg.get("writeDirs", defaults.get("writeDirs", [f".cache/{plat}/lulu-dev-workflow"]))

    return {
        "enable": bool(stage_enable),
        "bypassWriteWhenDelivered": bool(bypass),
        "readDirs": [expand_path_template(item, plat) for item in read_dirs],
        "writeDirs": [expand_path_template(item, plat) for item in write_dirs],
    }
