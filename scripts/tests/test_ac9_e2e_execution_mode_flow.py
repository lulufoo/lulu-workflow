#!/usr/bin/env python3
"""T-11 / AC-9: end-to-end execution_mode flow (start guided → internal switch)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_CYCLE_CONTROL = _SCRIPTS / "cycle_control.py"
_RUNTIME_CONTROL = _SCRIPTS / "runtime_control.py"
_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}


def _run_cycle_control(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(_CYCLE_CONTROL),
        "--project-root",
        str(tmp_path),
        *args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, env=_ENV_COPILOT)


def _run_runtime_control(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(_RUNTIME_CONTROL),
        "--project-root",
        str(tmp_path),
        *args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, env=_ENV_COPILOT)


def _cache_dir(tmp_path: Path) -> Path:
    return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"


def test_ac9_start_without_mode_defaults_guided(tmp_path):
    result = _run_cycle_control(tmp_path, "start", "--name", "ac9-e2e")
    assert result.returncode == 0, result.stderr
    cycle_id = result.stdout.strip().splitlines()[-1]
    data = json.loads((_cache_dir(tmp_path) / "cycles.json").read_text())
    assert data[cycle_id]["execution_mode"] == "guided"


def test_ac9_set_execution_mode_internal_gate(tmp_path):
    start = _run_cycle_control(tmp_path, "start", "--name", "ac9-e2e")
    assert start.returncode == 0, start.stderr
    cycle_id = start.stdout.strip().splitlines()[-1]

    rejected = _run_cycle_control(
        tmp_path,
        "set-execution-mode",
        "--cycle-id",
        cycle_id,
        "--mode",
        "autonomous",
    )
    assert rejected.returncode == 1
    payload = json.loads(rejected.stdout.strip())
    assert payload["ok"] is False
    assert "--internal" in payload["message"]

    accepted = _run_cycle_control(
        tmp_path,
        "set-execution-mode",
        "--cycle-id",
        cycle_id,
        "--mode",
        "autonomous",
        "--internal",
    )
    assert accepted.returncode == 0, accepted.stderr
    assert json.loads(accepted.stdout.strip()) == {
        "cycle_id": cycle_id,
        "execution_mode": "autonomous",
    }
    data = json.loads((_cache_dir(tmp_path) / "cycles.json").read_text())
    assert data[cycle_id]["execution_mode"] == "autonomous"


def test_ac9_runtime_control_internal_gate(tmp_path):
    start = _run_cycle_control(tmp_path, "start", "--name", "ac9-e2e")
    cycle_id = start.stdout.strip().splitlines()[-1]

    rejected = _run_runtime_control(
        tmp_path,
        "set-execution-mode",
        "--cycle-id",
        cycle_id,
        "--mode",
        "autonomous",
    )
    assert rejected.returncode == 1
    payload = json.loads(rejected.stdout.strip())
    assert payload["ok"] is False

    accepted = _run_runtime_control(
        tmp_path,
        "set-execution-mode",
        "--cycle-id",
        cycle_id,
        "--mode",
        "autonomous",
        "--internal",
    )
    assert accepted.returncode == 0, accepted.stderr
    data = json.loads((_cache_dir(tmp_path) / "cycles.json").read_text())
    assert data[cycle_id]["execution_mode"] == "autonomous"
