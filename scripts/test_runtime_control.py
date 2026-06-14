#!/usr/bin/env python3
"""Tests for runtime_control.py CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
_RUNTIME_CONTROL = _SCRIPTS / "runtime_control.py"
_ENV_CLEAN = {
    key: value
    for key, value in os.environ.items()
    if key not in {"LULU_PLATFORM", "COPILOT_AGENT", "CURSOR_AGENT", "VSCODE_TARGET_SESSION_LOG", "LULU_CONVERSATION_ID"}
}


def _run(*args: str, env=None):
    cmd = [sys.executable, str(_RUNTIME_CONTROL), *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env or _ENV_CLEAN)


class TestResolvePlatformContext:
    def test_defaults_to_cursor_without_signal(self, tmp_path: Path):
        result = _run(
            "--project-root",
            str(tmp_path),
            "resolve-platform-context",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip())
        assert payload["platform"] == "cursor"
        assert payload["workflow_dir"] == ".cursor/lulu-dev-workflow"
        assert payload["cache_dir"] == ".cache/cursor/lulu-dev-workflow"
        assert Path(payload["skill_root"]).name == "lulu-dev-workflow"

    def test_copilot_agent_signal(self, tmp_path: Path):
        env = {**_ENV_CLEAN, "COPILOT_AGENT": "1"}
        result = _run(
            "--project-root",
            str(tmp_path),
            "resolve-platform-context",
            env=env,
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout.strip())["platform"] == "copilot"


class TestResolveSessionContext:
    def test_empty_payload_without_conversation_id(self, tmp_path: Path):
        result = _run(
            "--project-root",
            str(tmp_path),
            "resolve-session-context",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip())
        assert payload == {
            "conversation_id": "",
            "cycle_id": "",
            "cycle_type": "",
            "stage": "",
            "execution_mode": "",
        }

    def test_full_payload_from_active_context_and_cycles(self, tmp_path: Path):
        env = {
            **_ENV_CLEAN,
            "LULU_CONVERSATION_ID": "conv-123",
        }
        cache = tmp_path / ".cache" / "cursor" / "lulu-dev-workflow"
        cache.mkdir(parents=True)
        cycle_id = "feature-20260101000000-11111111"
        (cache / "cycles.json").write_text(
            json.dumps({cycle_id: {"name": "demo", "execution_mode": "autonomous"}})
        )
        active = tmp_path / ".cache" / "cursor" / "lulu-dev-workflow" / "active-context.json"
        active.write_text(
            json.dumps(
                {
                    "conv-123": {
                        "cycle_id": cycle_id,
                        "stage": "tech-plan",
                        "cycle_type": "feature",
                    }
                }
            )
        )
        result = _run(
            "--project-root",
            str(tmp_path),
            "resolve-session-context",
            env=env,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip())
        assert payload["conversation_id"] == "conv-123"
        assert payload["cycle_id"] == cycle_id
        assert payload["cycle_type"] == "feature"
        assert payload["stage"] == "tech-plan"
        assert payload["execution_mode"] == "autonomous"

    def test_cli_conversation_id_overrides_env(self, tmp_path: Path):
        env = {
            **_ENV_CLEAN,
            "LULU_CONVERSATION_ID": "env-conv",
        }
        cache = tmp_path / ".cache" / "cursor" / "lulu-dev-workflow"
        cache.mkdir(parents=True)
        cycle_id = "feature-20260101000000-55555555"
        (cache / "cycles.json").write_text(
            json.dumps({cycle_id: {"name": "demo", "execution_mode": "guided"}})
        )
        active = cache / "active-context.json"
        active.write_text(
            json.dumps(
                {
                    "cli-conv": {
                        "cycle_id": cycle_id,
                        "stage": "tech-plan",
                        "cycle_type": "feature",
                    }
                }
            )
        )
        result = _run(
            "--project-root",
            str(tmp_path),
            "resolve-session-context",
            "--conversation-id",
            "cli-conv",
            env=env,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip())
        assert payload["conversation_id"] == "cli-conv"
        assert payload["cycle_id"] == cycle_id

    def test_execution_mode_defaults_guided_when_cycle_missing(self, tmp_path: Path):
        env = {
            **_ENV_CLEAN,
            "LULU_CONVERSATION_ID": "conv-456",
        }
        cache = tmp_path / ".cache" / "cursor" / "lulu-dev-workflow"
        cache.mkdir(parents=True)
        (cache / "cycles.json").write_text("{}")
        active = cache / "active-context.json"
        active.write_text(
            json.dumps(
                {
                    "conv-456": {
                        "cycle_id": "feature-20260101000000-22222222",
                        "stage": "tech-code",
                    }
                }
            )
        )
        result = _run(
            "--project-root",
            str(tmp_path),
            "resolve-session-context",
            env=env,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip())
        assert payload["execution_mode"] == "guided"


class TestSetExecutionModeFacade:
    def test_updates_cycles_json(self, tmp_path: Path):
        cache = tmp_path / ".cache" / "cursor" / "lulu-dev-workflow"
        cache.mkdir(parents=True)
        cycle_id = "feature-20260101000000-33333333"
        (cache / "cycles.json").write_text(
            json.dumps({cycle_id: {"name": "demo", "execution_mode": "guided"}})
        )
        result = _run(
            "--project-root",
            str(tmp_path),
            "set-execution-mode",
            "--cycle-id",
            cycle_id,
            "--mode",
            "autonomous",
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout.strip())
        assert payload == {"cycle_id": cycle_id, "execution_mode": "autonomous"}
        data = json.loads((cache / "cycles.json").read_text())
        assert data[cycle_id]["execution_mode"] == "autonomous"

    def test_unknown_cycle_exit_one(self, tmp_path: Path):
        cache = tmp_path / ".cache" / "cursor" / "lulu-dev-workflow"
        cache.mkdir(parents=True)
        (cache / "cycles.json").write_text("{}")
        result = _run(
            "--project-root",
            str(tmp_path),
            "set-execution-mode",
            "--cycle-id",
            "feature-20260101000000-44444444",
            "--mode",
            "guided",
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout.strip())
        assert payload["ok"] is False
        assert payload["command"] == "set-execution-mode"
