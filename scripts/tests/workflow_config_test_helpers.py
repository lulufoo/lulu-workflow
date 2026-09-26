#!/usr/bin/env python3
"""Shared helpers for workflow-config tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from platform_schema import PLATFORM_PATHS  # noqa: E402


def workflow_test_root(tmp_path: Path, platform: str = "cursor") -> Path:
    return tmp_path / PLATFORM_PATHS[platform]["workflow_dir"]


def write_stage_config(
    tmp_path: Path,
    stage: str,
    payload: dict,
    *,
    legacy: bool = False,
    platform: str = "cursor",
) -> Path:
    """Write workflow config for tests. Returns config root directory."""
    root = workflow_test_root(tmp_path, platform)
    root.mkdir(parents=True, exist_ok=True)

    if legacy:
        monolith_path = root / "workflow-config.json"
        monolith_path.write_text(json.dumps({stage: payload}), encoding="utf-8")
        return root

    stages_dir = root / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)
    (stages_dir / f"{stage}.json").write_text(json.dumps(payload), encoding="utf-8")
    manifest = root / "manifest.json"
    if not manifest.exists():
        manifest.write_text(
            json.dumps({"version": 1, "layout": "stages"}) + "\n",
            encoding="utf-8",
        )
    return root


def write_monolith_config(
    tmp_path: Path,
    payload: dict,
    *,
    platform: str = "cursor",
) -> Path:
    root = workflow_test_root(tmp_path, platform)
    root.mkdir(parents=True, exist_ok=True)
    monolith = root / "workflow-config.json"
    monolith.write_text(json.dumps(payload), encoding="utf-8")
    return monolith
