#!/usr/bin/env python3
"""Schema and I/O for workflow-guard-config.json (path guards + logs switch)."""

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

from workflow_config_schema import (  # noqa: E402
    detect_platform,
    resolve_workflow_config_root,
)

_HOOK_CONFIG_FILENAME = "workflow-guard-config.json"

_DEFAULT_HOOK_CONFIG: dict[str, Any] = {
    "version": 2,
    "logs": {
        "enabled": False,
    },
    "internalPathGuard": {
        "enable": True,
        "defaults": {
            "readDirs": ["."],
            "writeDirs": [".cache/{platform}/lulu-workflow"],
        },
        "stages": {
            "lulu-exec": {
                "readDirs": ["."],
                "writeDirs": ["."],
            },
        },
    },
    "externalPathGuard": {
        "enabled": False,
        "writeAllowExternalPaths": [],
        "readAllowExternalPaths": ["~/.cursor/", "~/.copilot/", "~/.claude/"],
        "sessionAllow": False,
    },
}


def default_hook_config() -> dict[str, Any]:
    """Return a deep copy of the built-in default workflow-guard-config payload."""
    return copy.deepcopy(_DEFAULT_HOOK_CONFIG)


def resolve_hook_config_path(
    project_root: Path,
    platform: Optional[str] = None,
) -> Path:
    """Return path to workflow-guard-config.json under $WORKFLOW_DIR."""
    return resolve_workflow_config_root(project_root, platform) / _HOOK_CONFIG_FILENAME


def validate_hook_config(data: object) -> list[str]:
    """Return validation error messages; empty list means valid."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["root must be a JSON object"]
    version = data.get("version")
    if version != 2:
        errors.append("version must be 2")

    internal = data.get("internalPathGuard")
    if not isinstance(internal, dict):
        errors.append("internalPathGuard must be an object")
        return errors

    enable = internal.get("enable")
    if enable is not None and not isinstance(enable, bool):
        errors.append("internalPathGuard.enable must be a boolean")

    defaults = internal.get("defaults")
    if defaults is not None:
        if not isinstance(defaults, dict):
            errors.append("internalPathGuard.defaults must be an object")
        else:
            errors.extend(
                _validate_dir_list(
                    defaults.get("readDirs"), "internalPathGuard.defaults.readDirs"
                )
            )
            errors.extend(
                _validate_dir_list(
                    defaults.get("writeDirs"), "internalPathGuard.defaults.writeDirs"
                )
            )

    stages = internal.get("stages")
    if stages is not None:
        if not isinstance(stages, dict):
            errors.append("internalPathGuard.stages must be an object")
        else:
            for stage, stage_cfg in stages.items():
                if not isinstance(stage_cfg, dict):
                    errors.append(f"internalPathGuard.stages.{stage} must be an object")
                    continue
                prefix = f"internalPathGuard.stages.{stage}"
                stage_enable = stage_cfg.get("enable")
                if stage_enable is not None and not isinstance(stage_enable, bool):
                    errors.append(f"{prefix}.enable must be a boolean")
                errors.extend(
                    _validate_dir_list(stage_cfg.get("readDirs"), f"{prefix}.readDirs")
                )
                errors.extend(
                    _validate_dir_list(stage_cfg.get("writeDirs"), f"{prefix}.writeDirs")
                )

    errors.extend(_validate_logs(data.get("logs")))
    errors.extend(_validate_external_path_guard(data.get("externalPathGuard")))
    return errors


def _validate_logs(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, dict):
        return ["logs must be an object"]
    enabled = value.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        return ["logs.enabled must be a boolean"]
    return []


def _validate_external_path_guard(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, dict):
        return ["externalPathGuard must be an object"]
    errors: list[str] = []
    enabled = value.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        errors.append("externalPathGuard.enabled must be a boolean")
    session_allow = value.get("sessionAllow")
    if session_allow is not None and not isinstance(session_allow, bool):
        errors.append("externalPathGuard.sessionAllow must be a boolean")
    errors.extend(
        _validate_dir_list(
            value.get("writeAllowExternalPaths"),
            "externalPathGuard.writeAllowExternalPaths",
        )
    )
    errors.extend(
        _validate_dir_list(
            value.get("readAllowExternalPaths"),
            "externalPathGuard.readAllowExternalPaths",
        )
    )
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
    """Load workflow-guard-config.json; missing or invalid file falls back to built-in default."""
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
    """Write default workflow-guard-config.json when missing. Returns (path, created)."""
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
    return path.replace("{platform}", plat)


def resolve_internal_path_guard(
    project_root: Path,
    stage: str,
    platform: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve effective internalPathGuard settings for a stage."""
    config = load_hook_config(project_root, platform)
    internal = config.get("internalPathGuard") or {}
    plat = detect_platform(platform)

    global_enable = internal.get("enable", True)
    defaults = internal.get("defaults") or {}
    stages = internal.get("stages") or {}
    stage_cfg = stages.get(stage) or {}
    if not stage_cfg:
        from stage_identity import stage_config_aliases

        for alias in stage_config_aliases(stage):
            if alias == stage:
                continue
            stage_cfg = stages.get(alias) or {}
            if stage_cfg:
                break

    stage_enable = stage_cfg.get("enable", global_enable)
    read_dirs = stage_cfg.get("readDirs", defaults.get("readDirs", ["."]))
    write_dirs = stage_cfg.get(
        "writeDirs",
        defaults.get("writeDirs", [f".cache/{plat}/lulu-workflow"]),
    )

    return {
        "enable": bool(stage_enable),
        "readDirs": [expand_path_template(item, plat) for item in read_dirs],
        "writeDirs": [expand_path_template(item, plat) for item in write_dirs],
    }


# Backward-compatible alias during rename.
resolve_rw_guard = resolve_internal_path_guard


def resolve_external_path_guard(
    project_root: Path,
    platform: Optional[str] = None,
) -> dict[str, Any]:
    """Resolve effective externalPathGuard settings."""
    config = load_hook_config(project_root, platform)
    external = config.get("externalPathGuard") or {}
    defaults = default_hook_config()["externalPathGuard"]
    return {
        "enabled": bool(external.get("enabled", defaults["enabled"])),
        "writeAllowExternalPaths": list(
            external.get(
                "writeAllowExternalPaths",
                defaults["writeAllowExternalPaths"],
            )
            or []
        ),
        "readAllowExternalPaths": list(
            external.get(
                "readAllowExternalPaths",
                defaults["readAllowExternalPaths"],
            )
            or []
        ),
        "sessionAllow": bool(external.get("sessionAllow", defaults["sessionAllow"])),
    }


def is_logs_enabled(
    project_root: Path,
    platform: Optional[str] = None,
) -> bool:
    """Return workflow observability switch from ``logs.enabled`` (default false)."""
    config = load_hook_config(project_root, platform)
    logs = config.get("logs") or {}
    return bool(logs.get("enabled", False))
