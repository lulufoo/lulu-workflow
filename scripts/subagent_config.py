#!/usr/bin/env python3
"""Shared subagent model resolution from workflow-config.json.

Thin re-export layer; implementation lives in workflow_config.py.
"""

from __future__ import annotations

from workflow_config import (  # noqa: F401
    default_platform_config,
    detect_platform,
    ensure_platform_config,
    extract_subagent_model,
    get_stage_config,
    load_workflow_config,
    platform_config_path,
    read_platform_config,
    resolve_subagent_model,
    resolve_workflow_config_path,
    write_platform_config,
)

__all__ = [
    "default_platform_config",
    "detect_platform",
    "ensure_platform_config",
    "extract_subagent_model",
    "get_stage_config",
    "load_workflow_config",
    "platform_config_path",
    "read_platform_config",
    "resolve_subagent_model",
    "resolve_workflow_config_path",
    "write_platform_config",
]
