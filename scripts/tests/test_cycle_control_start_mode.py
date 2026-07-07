#!/usr/bin/env python3
"""T-08: cycle_control start no longer accepts --mode; cmd_start always uses guided."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_CYCLE_CONTROL = _SCRIPTS / "cycle_control.py"
_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}


def _run(*args: str):
    cmd = [sys.executable, str(_CYCLE_CONTROL), *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=_ENV_COPILOT)


def _cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"


def test_start_rejects_mode_flag(tmp_path):
    result = _run(
        "--project-root",
        str(tmp_path),
        "start",
        "--name",
        "feat",
        "--mode",
        "autonomous",
    )
    assert result.returncode != 0
    assert "unrecognized" in result.stderr.lower() or "unknown" in result.stderr.lower()


def test_start_writes_guided_execution_mode(tmp_path):
    result = _run("--project-root", str(tmp_path), "start", "--name", "my-feature")
    assert result.returncode == 0, result.stderr
    cycle_id = result.stdout.strip().splitlines()[-1]
    data = json.loads((_cache_dir(tmp_path) / "cycles.json").read_text())
    assert data[cycle_id]["execution_mode"] == "guided"


def test_start_topic_type_is_guided(tmp_path):
    result = _run(
        "--project-root",
        str(tmp_path),
        "start",
        "--name",
        "my-topic",
        "--type",
        "topic",
    )
    assert result.returncode == 0, result.stderr
    cycle_id = result.stdout.strip().splitlines()[-1]
    data = json.loads((_cache_dir(tmp_path) / "cycles.json").read_text())
    assert data[cycle_id]["execution_mode"] == "guided"


def test_start_feature_with_topic_id_is_guided(tmp_path):
    topic = _run(
        "--project-root",
        str(tmp_path),
        "start",
        "--name",
        "parent-topic",
        "--type",
        "topic",
    )
    topic_id = topic.stdout.strip().splitlines()[-1]
    result = _run(
        "--project-root",
        str(tmp_path),
        "start",
        "--name",
        "child-feature",
        "--topic-id",
        topic_id,
    )
    assert result.returncode == 0, result.stderr
    cycle_id = result.stdout.strip().splitlines()[-1]
    data = json.loads((_cache_dir(tmp_path) / "cycles.json").read_text())
    assert data[cycle_id]["execution_mode"] == "guided"
