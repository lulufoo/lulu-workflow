#!/usr/bin/env python3
"""Tests for subagent_config.py."""

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


class TestDefaults:
    def test_default_platform_config(self):
        from subagent_config import default_platform_config

        cfg = default_platform_config()
        assert cfg["version"] == 1
        assert cfg["workflowConfig"] == "skill-config/lulu-dev-workflow/workflow-config.json"
        assert cfg["hookConfig"] == "skill-config/lulu-dev-workflow/hook-config.json"
        assert "subagents" not in cfg


class TestResolveSubagentModel:
    def _write_workflow_config(self, tmp_path: Path, payload: dict) -> None:
        cfg_path = tmp_path / "skill-config/lulu-dev-workflow/workflow-config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    def _write_platform_config(self, tmp_path: Path, payload: dict, platform: str = "cursor") -> None:
        rel = ".cursor/lulu-dev-workflow" if platform == "cursor" else ".github/lulu-dev-workflow"
        cfg_path = tmp_path / rel / "config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_returns_model_for_cursor(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_workflow_config(tmp_path, {
            "tech-code": {"subagent": {"cursor": "Auto", "copilot": "GPT-5.4"}}
        })
        assert resolve_subagent_model(tmp_path, "tech-code", "cursor") == "Auto"

    def test_returns_model_for_copilot(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_workflow_config(tmp_path, {
            "tech-code": {"subagent": {"cursor": "Auto", "copilot": "GPT-5.4"}}
        })
        assert resolve_subagent_model(tmp_path, "tech-code", "copilot") == "GPT-5.4"

    def test_missing_platform_key_returns_none(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_workflow_config(tmp_path, {
            "tech-code": {"subagent": {"cursor": "Auto"}}
        })
        assert resolve_subagent_model(tmp_path, "tech-code", "copilot") is None

    def test_empty_string_returns_none(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_workflow_config(tmp_path, {
            "tech-code": {"subagent": {"cursor": ""}}
        })
        assert resolve_subagent_model(tmp_path, "tech-code", "cursor") is None

    def test_whitespace_only_returns_none(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_workflow_config(tmp_path, {
            "tech-code": {"subagent": {"cursor": "   "}}
        })
        assert resolve_subagent_model(tmp_path, "tech-code", "cursor") is None

    def test_missing_subagent_key_returns_none(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_workflow_config(tmp_path, {
            "tech-code": {"test_command": "npm test"}
        })
        assert resolve_subagent_model(tmp_path, "tech-code", "cursor") is None

    def test_missing_stage_returns_none(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_workflow_config(tmp_path, {})
        assert resolve_subagent_model(tmp_path, "tech-code", "cursor") is None

    def test_missing_workflow_config_returns_none(self, tmp_path):
        from subagent_config import resolve_subagent_model

        assert resolve_subagent_model(tmp_path, "tech-code", "cursor") is None

    def test_invalid_workflow_config_json_returns_none(self, tmp_path):
        from subagent_config import resolve_subagent_model

        cfg_path = tmp_path / "skill-config/lulu-dev-workflow/workflow-config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text("{not json", encoding="utf-8")
        assert resolve_subagent_model(tmp_path, "tech-code", "cursor") is None

    def test_custom_workflow_config_path_from_platform_config(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_platform_config(tmp_path, {
            "workflowConfig": "custom/my-config.json"
        }, platform="cursor")
        cfg_path = tmp_path / "custom/my-config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps({
            "tech-code": {"subagent": {"cursor": "Auto"}}
        }), encoding="utf-8")
        assert resolve_subagent_model(tmp_path, "tech-code", "cursor") == "Auto"


class TestPlatformConfigPath:
    def test_cursor_path(self, tmp_path):
        from subagent_config import platform_config_path

        assert platform_config_path(tmp_path, "cursor") == (
            tmp_path / ".cursor/lulu-dev-workflow/config.json"
        )

    def test_copilot_path(self, tmp_path):
        from subagent_config import platform_config_path

        assert platform_config_path(tmp_path, "copilot") == (
            tmp_path / ".github/lulu-dev-workflow/config.json"
        )


class TestResolveWorkflowConfigPath:
    def test_default_path_when_platform_config_missing(self, tmp_path):
        from subagent_config import resolve_workflow_config_path

        assert resolve_workflow_config_path(tmp_path, "cursor") == (
            tmp_path / "skill-config/lulu-dev-workflow/workflow-config.json"
        )

    def test_custom_path_from_platform_config(self, tmp_path):
        from subagent_config import resolve_workflow_config_path

        cfg_path = tmp_path / ".cursor/lulu-dev-workflow/config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps({"workflowConfig": "custom/workflow-config.json"}),
            encoding="utf-8",
        )
        assert resolve_workflow_config_path(tmp_path, "cursor") == (
            tmp_path / "custom/workflow-config.json"
        )


class TestEnsurePlatformConfig:
    def test_creates_default_when_missing(self, tmp_path):
        from subagent_config import ensure_platform_config, read_platform_config

        ensure_platform_config(tmp_path, platform="cursor")
        cfg = read_platform_config(tmp_path, platform="cursor")
        assert cfg["workflowConfig"] == "skill-config/lulu-dev-workflow/workflow-config.json"
        assert cfg["hookConfig"] == "skill-config/lulu-dev-workflow/hook-config.json"
        assert "subagents" not in cfg

    def test_does_not_overwrite_existing_config(self, tmp_path):
        from subagent_config import ensure_platform_config, read_platform_config

        cfg_path = tmp_path / ".cursor/lulu-dev-workflow/config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps({"version": 1, "workflowConfig": "custom/workflow-config.json"}),
            encoding="utf-8",
        )
        ensure_platform_config(tmp_path, platform="cursor")
        cfg = read_platform_config(tmp_path, platform="cursor")
        assert cfg["workflowConfig"] == "custom/workflow-config.json"


class TestResolveSubagentCli:
    def _write_workflow_config(self, tmp_path: Path, payload: dict) -> None:
        cfg_path = tmp_path / "skill-config/lulu-dev-workflow/workflow-config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_stdout_json_with_model(self, tmp_path):
        import subprocess
        self._write_workflow_config(tmp_path, {
            "tech-code": {"subagent": {"cursor": "Auto", "copilot": "GPT-5.4"}}
        })

        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "workflow_config.py"),
                "get-model",
                "--project-root",
                str(tmp_path),
                "--stage",
                "tech-code",
                "--platform",
                "cursor",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert json.loads(result.stdout.strip()) == {"model": "Auto"}

    def test_stdout_empty_object_without_model(self, tmp_path):
        import subprocess
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "workflow_config.py"),
                "get-model",
                "--project-root",
                str(tmp_path),
                "--stage",
                "tech-code",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert json.loads(result.stdout.strip()) == {}

    def test_missing_required_args_nonzero_exit(self):
        import subprocess
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "workflow_config.py"), "get-model"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
