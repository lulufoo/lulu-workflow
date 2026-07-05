#!/usr/bin/env python3
"""Shared helpers for workflow-config tests."""

from __future__ import annotations

import json
from pathlib import Path


def write_stage_config(
    tmp_path: Path,
    stage: str,
    payload: dict,
    *,
    legacy: bool = False,
) -> Path:
    """Write workflow config for tests. Returns config root directory."""
    root = tmp_path / "skill-config" / "lulu-dev-workflow"
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


def write_monolith_config(tmp_path: Path, payload: dict) -> Path:
    root = tmp_path / "skill-config" / "lulu-dev-workflow"
    root.mkdir(parents=True, exist_ok=True)
    monolith = root / "workflow-config.json"
    monolith.write_text(json.dumps(payload), encoding="utf-8")
    return monolith
