#!/usr/bin/env python3
"""Tests for subagent_config.py."""

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


class TestDefaults:
    def test_default_platform_config(self):
        from subagent_config import default_platform_config

        cfg = default_platform_config()
        assert cfg["version"] == 1
        assert "workflowConfig" not in cfg
        assert "hookConfig" not in cfg
        assert "logsConfig" not in cfg
        assert "subagents" not in cfg


class TestPlatformConfigPath:
    def test_cursor_path(self, tmp_path):
        from subagent_config import platform_config_path

        assert platform_config_path(tmp_path, "cursor") == (
            tmp_path / ".cursor/lulu-workflow/config.json"
        )

    def test_copilot_path(self, tmp_path):
        from subagent_config import platform_config_path

        assert platform_config_path(tmp_path, "copilot") == (
            tmp_path / ".github/lulu-workflow/config.json"
        )


class TestResolveWorkflowConfigPath:
    def test_default_path_when_platform_config_missing(self, tmp_path):
        from subagent_config import resolve_workflow_config_path

        assert resolve_workflow_config_path(tmp_path, "cursor") == (
            tmp_path / ".cursor/lulu-workflow"
        )

    def test_leftover_pointer_does_not_change_root(self, tmp_path):
        from subagent_config import resolve_workflow_config_path

        cfg_path = tmp_path / ".cursor/lulu-workflow/config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps({"workflowConfig": "custom/workflow-config.json"}),
            encoding="utf-8",
        )
        assert resolve_workflow_config_path(tmp_path, "cursor") == (
            tmp_path / ".cursor/lulu-workflow"
        )


class TestEnsurePlatformConfig:
    def test_creates_default_when_missing(self, tmp_path):
        from subagent_config import ensure_platform_config, read_platform_config

        ensure_platform_config(tmp_path, platform="cursor")
        cfg = read_platform_config(tmp_path, platform="cursor")
        assert cfg == {}
        assert not (
            tmp_path / ".cursor/lulu-workflow/config.json"
        ).exists()

    def test_does_not_overwrite_existing_config(self, tmp_path):
        from subagent_config import ensure_platform_config, read_platform_config

        cfg_path = tmp_path / ".cursor/lulu-workflow/config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps({"version": 1, "workflowConfig": "custom/workflow-config.json"}),
            encoding="utf-8",
        )
        ensure_platform_config(tmp_path, platform="cursor")
        cfg = read_platform_config(tmp_path, platform="cursor")
        assert cfg["workflowConfig"] == "custom/workflow-config.json"
