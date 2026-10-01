#!/usr/bin/env python3
"""Tests for runtime_control.py CLI."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
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
        assert payload["project_root"] == str(tmp_path.resolve())
        assert payload["workflow_dir"] == ".agents/config/lulu-workflow"
        assert payload["cache_dir"] == ".cache/cursor/lulu-workflow"
        assert Path(payload["skill_root"]).name == "lulu-workflow"

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
        }

    def test_full_payload_from_active_context_and_cycles(self, tmp_path: Path):
        env = {
            **_ENV_CLEAN,
            "LULU_CONVERSATION_ID": "conv-123",
        }
        cache = tmp_path / ".cache" / "cursor" / "lulu-workflow"
        cache.mkdir(parents=True)
        cycle_id = "feature-20260101000000-11111111"
        (cache / "cycles.json").write_text(
            json.dumps({cycle_id: {"name": "demo"}})
        )
        active = tmp_path / ".cache" / "cursor" / "lulu-workflow" / "active-context.json"
        active.write_text(
            json.dumps(
                {
                    "conv-123": {
                        "cycle_id": cycle_id,
                        "stage": "lulu-plan",
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
        assert payload["stage"] == "lulu-plan"

    def test_cli_conversation_id_overrides_env(self, tmp_path: Path):
        env = {
            **_ENV_CLEAN,
            "LULU_CONVERSATION_ID": "env-conv",
        }
        cache = tmp_path / ".cache" / "cursor" / "lulu-workflow"
        cache.mkdir(parents=True)
        cycle_id = "feature-20260101000000-55555555"
        (cache / "cycles.json").write_text(
            json.dumps({cycle_id: {"name": "demo"}})
        )
        active = cache / "active-context.json"
        active.write_text(
            json.dumps(
                {
                    "cli-conv": {
                        "cycle_id": cycle_id,
                        "stage": "lulu-plan",
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
