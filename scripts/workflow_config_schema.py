#!/usr/bin/env python3
"""Authoritative I/O for workflow-config.json and platform config pointer.

Library module — CLI lives in workflow_config.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from platform_schema import PLATFORM_PATHS, detect_platform as _detect_platform

_WORKFLOW_DIR_MAP = {
    platform: paths["workflow_dir"] for platform, paths in PLATFORM_PATHS.items()
}

_DEFAULT_WORKFLOW_CONFIG_PATH = "skill-config/lulu-dev-workflow/workflow-config.json"
_DEFAULT_CONFIGURE_BLOB_URL = (
    "https://github.com/lulufoo/lulu-workflow-framework/blob/main/template/workflow-config.json"
)


def detect_platform(platform: Optional[str] = None) -> str:
    return _detect_platform(override=platform, strict=False)


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


def resolve_workflow_config_path(
    project_root: Path,
    platform: Optional[str] = None,
) -> Path:
    """Return path to workflow-config.json via platform config pointer."""
    platform_cfg = read_platform_config(project_root, platform)
    workflow_config_rel = platform_cfg.get("workflowConfig", _DEFAULT_WORKFLOW_CONFIG_PATH)
    return project_root / workflow_config_rel


def load_workflow_config(project_root: Path, platform: Optional[str] = None) -> dict:
    """Load and parse workflow-config.json. Raises ValueError if missing or unreadable."""
    workflow_config_path = resolve_workflow_config_path(project_root, platform)
    if not workflow_config_path.exists():
        raise ValueError(f"workflow-config.json not found: {workflow_config_path}")
    try:
        return json.loads(workflow_config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"workflow-config.json unreadable: {workflow_config_path}") from exc


def get_stage_config(project_root: Path, stage: str, platform: Optional[str] = None) -> dict:
    config = load_workflow_config(project_root, platform)
    return config.get(stage) or {}


def extract_subagent_model(
    stage_cfg: dict,
    platform: Optional[str] = None,
) -> Optional[str]:
    """Extract optional subagent model slug from a pre-loaded stage config dict."""
    plat = detect_platform(platform)
    subagent = stage_cfg.get("subagent") or {}
    model = subagent.get(plat)
    if model is None:
        return None
    stripped = str(model).strip()
    return stripped if stripped else None


def resolve_subagent_model(
    project_root: Path,
    stage: str,
    platform: Optional[str] = None,
) -> Optional[str]:
    workflow_config_path = resolve_workflow_config_path(project_root, platform)

    if not workflow_config_path.exists():
        return None
    try:
        workflow_config = json.loads(workflow_config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    stage_cfg = workflow_config.get(stage) or {}
    return extract_subagent_model(stage_cfg, platform)


def apply_workflow_config_from_url(
    project_root: Path,
    url: str,
    *,
    platform: Optional[str] = None,
) -> Path:
    """Download workflow-config JSON from a GitHub blob URL and write to resolved path."""
    from fetch_template import atomic_write, gh_api_fetch, parse_blob_url  # noqa: WPS433

    parsed = parse_blob_url(url.strip())
    content = gh_api_fetch(
        parsed["owner"],
        parsed["repo"],
        parsed["ref"],
        parsed["path"],
    )
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"downloaded workflow-config is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("downloaded workflow-config root must be a JSON object")

    normalized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    target = resolve_workflow_config_path(project_root, platform)
    atomic_write(target, normalized)
    return target


def default_configure_blob_url() -> str:
    return _DEFAULT_CONFIGURE_BLOB_URL
