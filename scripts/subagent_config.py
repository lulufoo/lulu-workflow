#!/usr/bin/env python3
"""Shared subagent model resolution from platform config.json."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Optional

DEFAULT_SUBAGENTS = {"code": {"model": ""}}

_WORKFLOW_DIR_MAP = {
    "cursor": Path(".cursor/lulu-dev-workflow"),
    "copilot": Path(".github/lulu-dev-workflow"),
}


def detect_platform(platform: Optional[str] = None) -> str:
    if platform:
        return platform
    return (
        os.environ.get("LULU_PLATFORM")
        or ("copilot" if os.environ.get("COPILOT_AGENT") else "cursor")
    )


def default_subagents() -> dict:
    return deepcopy(DEFAULT_SUBAGENTS)


def default_platform_config() -> dict:
    return {
        "version": 1,
        "workflowConfig": "skill-config/lulu-dev-workflow/workflow-config.json",
        "subagents": default_subagents(),
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


def ensure_subagents_section(cfg: dict) -> dict:
    out = dict(cfg)
    if "subagents" not in out:
        out["subagents"] = default_subagents()
    return out


def resolve_subagent_model(
    project_root: Path,
    stage: str,
    platform: Optional[str] = None,
) -> Optional[str]:
    cfg = read_platform_config(project_root, platform)
    subagents = cfg.get("subagents")
    if not subagents:
        return None

    default_cfg = subagents.get("default") or {}
    stage_cfg = subagents.get(stage) or {}
    merged = {**default_cfg, **stage_cfg}
    model = merged.get("model")
    if model is None:
        return None

    stripped = str(model).strip()
    return stripped if stripped else None
