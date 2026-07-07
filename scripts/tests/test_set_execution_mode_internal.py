#!/usr/bin/env python3
"""T-09: set-execution-mode requires --internal in cycle_control and runtime_control."""

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
_ENV_CLEAN = {
    key: value
    for key, value in os.environ.items()
    if key
    not in {
        "LULU_PLATFORM",
        "COPILOT_AGENT",
        "CURSOR_AGENT",
        "VSCODE_TARGET_SESSION_LOG",
        "LULU_CONVERSATION_ID",
    }
}


def _run_cycle_control(*args: str):
    cmd = [sys.executable, str(_CYCLE_CONTROL), *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=_ENV_COPILOT)


def _run_runtime_control(*args: str):
    cmd = [sys.executable, str(_RUNTIME_CONTROL), *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=_ENV_CLEAN)


def _cache_dir(tmp_path: Path, platform: str = "copilot") -> Path:
    return tmp_path / ".cache" / platform / "lulu-dev-workflow"


def _start_cycle(tmp_path: Path) -> str:
    result = _run_cycle_control("--project-root", str(tmp_path), "start", "--name", "feat")
    assert result.returncode == 0, result.stderr
    return result.stdout.strip().splitlines()[-1]


def test_cycle_control_set_execution_mode_with_internal_succeeds(tmp_path):
    cycle_id = _start_cycle(tmp_path)
    result = _run_cycle_control(
        "--project-root",
        str(tmp_path),
        "set-execution-mode",
        "--cycle-id",
        cycle_id,
        "--mode",
        "autonomous",
        "--internal",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload == {"cycle_id": cycle_id, "execution_mode": "autonomous"}
    data = json.loads((_cache_dir(tmp_path) / "cycles.json").read_text())
    assert data[cycle_id]["execution_mode"] == "autonomous"


def test_cycle_control_set_execution_mode_guided_with_internal_succeeds(tmp_path):
    cycle_id = _start_cycle(tmp_path)
    result = _run_cycle_control(
        "--project-root",
        str(tmp_path),
        "set-execution-mode",
        "--cycle-id",
        cycle_id,
        "--mode",
        "guided",
        "--internal",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload == {"cycle_id": cycle_id, "execution_mode": "guided"}


def test_cycle_control_set_execution_mode_without_internal_rejected(tmp_path):
    cycle_id = _start_cycle(tmp_path)
    result = _run_cycle_control(
        "--project-root",
        str(tmp_path),
        "set-execution-mode",
        "--cycle-id",
        cycle_id,
        "--mode",
        "autonomous",
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is False
    assert payload["command"] == "set-execution-mode"


def test_runtime_control_set_execution_mode_with_internal_succeeds(tmp_path):
    cache = _cache_dir(tmp_path, "cursor")
    cache.mkdir(parents=True)
    cycle_id = "feature-20260101000000-33333333"
    (cache / "cycles.json").write_text(
        json.dumps({cycle_id: {"name": "demo", "execution_mode": "guided"}})
    )
    result = _run_runtime_control(
        "--project-root",
        str(tmp_path),
        "set-execution-mode",
        "--cycle-id",
        cycle_id,
        "--mode",
        "autonomous",
        "--internal",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.strip())
    assert payload == {"cycle_id": cycle_id, "execution_mode": "autonomous"}
    data = json.loads((cache / "cycles.json").read_text())
    assert data[cycle_id]["execution_mode"] == "autonomous"


def test_runtime_control_set_execution_mode_without_internal_rejected(tmp_path):
    cache = _cache_dir(tmp_path, "cursor")
    cache.mkdir(parents=True)
    cycle_id = "feature-20260101000000-44444444"
    (cache / "cycles.json").write_text(
        json.dumps({cycle_id: {"name": "demo", "execution_mode": "guided"}})
    )
    result = _run_runtime_control(
        "--project-root",
        str(tmp_path),
        "set-execution-mode",
        "--cycle-id",
        cycle_id,
        "--mode",
        "autonomous",
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout.strip())
    assert payload["ok"] is False
    assert payload["command"] == "set-execution-mode"
