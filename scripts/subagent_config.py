#!/usr/bin/env python3
"""Shared subagent model resolution from workflow-config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

_WORKFLOW_DIR_MAP = {
    "cursor": Path(".cursor/lulu-dev-workflow"),
    "copilot": Path(".github/lulu-dev-workflow"),
}

_DEFAULT_WORKFLOW_CONFIG_PATH = "skill-config/lulu-dev-workflow/workflow-config.json"


def detect_platform(platform: Optional[str] = None) -> str:
    if platform:
        return platform
    return (
        os.environ.get("LULU_PLATFORM")
        or ("copilot" if os.environ.get("COPILOT_AGENT") else "cursor")
    )


def default_platform_config() -> dict:
    return {
        "version": 1,
        "workflowConfig": _DEFAULT_WORKFLOW_CONFIG_PATH,
    }


def platform_config_path(project_root: Path, platform: Optional[str] = None) -> Path:
    plat = detect_platform(platform)
    workflow_dir = _WORKFLOW_DIR_MAP.get(plat, _WORKFLOW_DIR_MAP["cursor"])
    return project_root / workflow_dir / "config.json"


def read_platform_config(project_root: Path, platform: Optional[str] = None) -> dict:
    cfg_path = platform_config_path(project_root, platform)
    if not cfg_path.exists():
        return {}
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def write_platform_config(
    project_root: Path,
    cfg: dict,
    platform: Optional[str] = None,
) -> None:
    cfg_path = platform_config_path(project_root, platform)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def ensure_platform_config(project_root: Path, platform: Optional[str] = None) -> None:
    cfg_path = platform_config_path(project_root, platform)
    if not cfg_path.exists():
        write_platform_config(project_root, default_platform_config(), platform)


def resolve_subagent_model(
    project_root: Path,
    stage: str,
    platform: Optional[str] = None,
) -> Optional[str]:
    plat = detect_platform(platform)

    platform_cfg = read_platform_config(project_root, platform)
    workflow_config_rel = platform_cfg.get("workflowConfig", _DEFAULT_WORKFLOW_CONFIG_PATH)
    workflow_config_path = project_root / workflow_config_rel

    if not workflow_config_path.exists():
        return None
    try:
        workflow_config = json.loads(workflow_config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    stage_cfg = workflow_config.get(stage) or {}
    subagent = stage_cfg.get("subagent") or {}
    model = subagent.get(plat)
    if model is None:
        return None

    stripped = str(model).strip()
    return stripped if stripped else None
