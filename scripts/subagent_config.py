#!/usr/bin/env python3
"""Shared subagent model resolution from workflow-config.

Thin re-export layer; implementation lives in workflow_config_schema.py.
"""

from __future__ import annotations

from workflow_config_schema import (  # noqa: F401
    apply_workflow_config_from_url,
    default_configure_blob_url,
    default_platform_config,
    detect_platform,
    ensure_platform_config,
    extract_subagent_model,
    get_stage_config,
    get_stage_config_bucket,
    get_stage_config_value,
    load_stage_config,
    load_workflow_config,
    lookup_stage_config_value,
    platform_config_path,
    read_platform_config,
    resolve_stage_config_path,
    resolve_subagent_model,
    resolve_workflow_config_path,
    resolve_workflow_config_root,
    stage_config_has_key,
    workflow_config_is_present,
    write_platform_config,
)

__all__ = [
    "apply_workflow_config_from_url",
    "default_configure_blob_url",
    "default_platform_config",
    "detect_platform",
    "ensure_platform_config",
    "extract_subagent_model",
    "get_stage_config",
    "get_stage_config_bucket",
    "get_stage_config_value",
    "load_stage_config",
    "load_workflow_config",
    "lookup_stage_config_value",
    "platform_config_path",
    "read_platform_config",
    "resolve_stage_config_path",
    "resolve_subagent_model",
    "resolve_workflow_config_path",
    "resolve_workflow_config_root",
    "stage_config_has_key",
    "workflow_config_is_present",
    "write_platform_config",
]
