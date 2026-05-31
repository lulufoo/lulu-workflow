#!/usr/bin/env python3
"""Tests for subagent_config.py — TDD Red phase (t1)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


class TestDefaults:
    def test_default_subagents_skeleton(self):
        from subagent_config import DEFAULT_SUBAGENTS, default_subagents

        assert DEFAULT_SUBAGENTS == {"code": {"model": ""}}
        assert default_subagents() == {"code": {"model": ""}}

    def test_default_platform_config(self):
        from subagent_config import default_platform_config

        cfg = default_platform_config()
        assert cfg["version"] == 1
        assert cfg["workflowConfig"] == "skill-config/lulu-dev-workflow/workflow-config.json"
        assert cfg["subagents"] == {"code": {"model": ""}}


class TestEnsureSubagentsSection:
    def test_appends_subagents_when_missing(self):
        from subagent_config import ensure_subagents_section

        cfg = {"version": 1}
        result = ensure_subagents_section(cfg)
        assert result["subagents"] == {"code": {"model": ""}}
        assert "subagents" not in cfg

    def test_does_not_overwrite_existing_subagents(self):
        from subagent_config import ensure_subagents_section

        cfg = {"subagents": {"code": {"model": "gpt-5.3-codex"}}}
        result = ensure_subagents_section(cfg)
        assert result["subagents"]["code"]["model"] == "gpt-5.3-codex"


class TestResolveSubagentModel:
    def _write_config(self, tmp_path: Path, payload: dict, platform: str = "cursor") -> None:
        rel = ".cursor/lulu-dev-workflow" if platform == "cursor" else ".github/lulu-dev-workflow"
        cfg_path = tmp_path / rel / "config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(payload), encoding="utf-8")

    def test_returns_model_when_configured(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_config(
            tmp_path,
            {"subagents": {"code": {"model": "gpt-5.3-codex"}}},
        )
        assert resolve_subagent_model(tmp_path, "code") == "gpt-5.3-codex"

    def test_stage_overrides_default(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_config(
            tmp_path,
            {
                "subagents": {
                    "default": {"model": "gpt-5.5-medium"},
                    "code": {"model": "gpt-5.3-codex"},
                }
            },
        )
        assert resolve_subagent_model(tmp_path, "code") == "gpt-5.3-codex"

    def test_default_model_when_stage_empty(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_config(
            tmp_path,
            {
                "subagents": {
                    "default": {"model": "gpt-5.5-medium"},
                    "code": {"model": ""},
                }
            },
        )
        assert resolve_subagent_model(tmp_path, "code") is None

    def test_only_default_has_model(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_config(
            tmp_path,
            {"subagents": {"default": {"model": "gpt-5.5-medium"}}},
        )
        assert resolve_subagent_model(tmp_path, "code") == "gpt-5.5-medium"

    def test_empty_string_returns_none(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_config(tmp_path, {"subagents": {"code": {"model": ""}}})
        assert resolve_subagent_model(tmp_path, "code") is None

    def test_whitespace_only_returns_none(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_config(tmp_path, {"subagents": {"code": {"model": "   "}}})
        assert resolve_subagent_model(tmp_path, "code") is None

    def test_missing_config_file_returns_none(self, tmp_path):
        from subagent_config import resolve_subagent_model

        assert resolve_subagent_model(tmp_path, "code") is None

    def test_missing_subagents_key_returns_none(self, tmp_path):
        from subagent_config import resolve_subagent_model

        self._write_config(tmp_path, {"version": 1})
        assert resolve_subagent_model(tmp_path, "code") is None

    def test_invalid_json_returns_none(self, tmp_path):
        from subagent_config import resolve_subagent_model

        cfg_path = tmp_path / ".cursor/lulu-dev-workflow/config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text("{not json", encoding="utf-8")
        assert resolve_subagent_model(tmp_path, "code") is None


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


class TestEnsurePlatformConfig:
    def test_creates_default_when_missing(self, tmp_path):
        from subagent_config import ensure_platform_config, read_platform_config

        ensure_platform_config(tmp_path, platform="cursor")
        cfg = read_platform_config(tmp_path, platform="cursor")
        assert cfg["subagents"] == {"code": {"model": ""}}
        assert cfg["workflowConfig"] == "skill-config/lulu-dev-workflow/workflow-config.json"

    def test_migrate_preserves_workflow_config(self, tmp_path):
        from subagent_config import ensure_platform_config, read_platform_config

        cfg_path = tmp_path / ".cursor/lulu-dev-workflow/config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "workflowConfig": "custom/workflow-config.json",
                }
            ),
            encoding="utf-8",
        )
        ensure_platform_config(tmp_path, platform="cursor")
        cfg = read_platform_config(tmp_path, platform="cursor")
        assert cfg["workflowConfig"] == "custom/workflow-config.json"
        assert cfg["subagents"] == {"code": {"model": ""}}

    def test_does_not_overwrite_existing_subagents(self, tmp_path):
        from subagent_config import ensure_platform_config, read_platform_config

        cfg_path = tmp_path / ".cursor/lulu-dev-workflow/config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "subagents": {"code": {"model": "gpt-5.3-codex"}},
                }
            ),
            encoding="utf-8",
        )
        ensure_platform_config(tmp_path, platform="cursor")
        cfg = read_platform_config(tmp_path, platform="cursor")
        assert cfg["subagents"]["code"]["model"] == "gpt-5.3-codex"


class TestResolveSubagentCli:
    def test_stdout_json_with_model(self, tmp_path):
        cfg_path = tmp_path / ".cursor/lulu-dev-workflow/config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps({"subagents": {"code": {"model": "gpt-5.3-codex"}}}),
            encoding="utf-8",
        )

        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "resolve_subagent.py"),
                "--project-root",
                str(tmp_path),
                "--stage",
                "code",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert json.loads(result.stdout.strip()) == {"model": "gpt-5.3-codex"}

    def test_stdout_empty_object_without_model(self, tmp_path):
        result = subprocess.run(
            [
                sys.executable,
                str(_SCRIPTS / "resolve_subagent.py"),
                "--project-root",
                str(tmp_path),
                "--stage",
                "code",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert json.loads(result.stdout.strip()) == {}

    def test_missing_required_args_nonzero_exit(self):
        result = subprocess.run(
            [sys.executable, str(_SCRIPTS / "resolve_subagent.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0
