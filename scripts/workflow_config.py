#!/usr/bin/env python3
"""Canonical workflow-config.json access for lulu-dev-workflow."""

from __future__ import annotations

import argparse
import json
import os
import sys
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


def _cmd_get_model(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Resolve subagent model for a workflow stage.")
    parser.add_argument("--project-root", required=True, help="Project root directory.")
    parser.add_argument("--stage", required=True, help="Workflow stage name (e.g. tech-code).")
    parser.add_argument(
        "--platform",
        default=None,
        choices=["cursor", "copilot"],
        help="Platform override (default: auto-detect).",
    )
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    model = resolve_subagent_model(project_root, args.stage, args.platform)
    if model:
        print(json.dumps({"model": model}, ensure_ascii=False))
    else:
        print("{}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        parser = argparse.ArgumentParser(description="Workflow config utilities.")
        subparsers = parser.add_subparsers(dest="command")
        subparsers.add_parser("get-model", help="Resolve subagent model for a workflow stage.")
        parser.print_help()
        return 0 if not argv else 2

    if argv[0] == "get-model":
        return _cmd_get_model(argv[1:])

    print(f"Unknown command: {argv[0]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
