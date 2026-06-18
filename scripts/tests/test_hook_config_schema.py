#!/usr/bin/env python3
"""Tests for scripts/hook/hook_config_schema.py."""

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_HOOK = _SCRIPTS / "hook"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_HOOK) not in sys.path:
    sys.path.insert(0, str(_HOOK))


class TestDefaultHookConfig:
    def test_version_and_rw_guard(self):
        from hook_config_schema import default_hook_config

        cfg = default_hook_config()
        assert cfg["version"] == 1
        assert cfg["rwGuard"]["enable"] is True
        assert cfg["rwGuard"]["bypassWriteWhenDelivered"] is True

    def test_returns_deep_copy(self):
        from hook_config_schema import default_hook_config

        first = default_hook_config()
        second = default_hook_config()
        first["rwGuard"]["enable"] = False
        assert second["rwGuard"]["enable"] is True

    def test_includes_tech_code_stage(self):
        from hook_config_schema import default_hook_config

        stages = default_hook_config()["rwGuard"]["stages"]
        assert stages == {
            "tech-code": {
                "readDirs": ["."],
                "writeDirs": ["."],
            },
        }


class TestValidateHookConfig:
    def test_valid_default(self):
        from hook_config_schema import default_hook_config, validate_hook_config

        assert validate_hook_config(default_hook_config()) == []

    def test_rejects_non_object_root(self):
        from hook_config_schema import validate_hook_config

        assert validate_hook_config([]) == ["root must be a JSON object"]

    def test_rejects_bad_version(self):
        from hook_config_schema import validate_hook_config

        errors = validate_hook_config({"version": 2, "rwGuard": {}})
        assert "version must be 1" in errors


class TestResolveHookConfigPath:
    def test_default_path_when_platform_config_missing(self, tmp_path: Path):
        from hook_config_schema import resolve_hook_config_path

        assert resolve_hook_config_path(tmp_path, "cursor") == (
            tmp_path / "skill-config/lulu-dev-workflow/hook-config.json"
        )

    def test_custom_path_from_platform_config(self, tmp_path: Path):
        from hook_config_schema import resolve_hook_config_path

        cfg_path = tmp_path / ".cursor/lulu-dev-workflow/config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps({"hookConfig": "custom/hook-config.json"}),
            encoding="utf-8",
        )
        assert resolve_hook_config_path(tmp_path, "cursor") == (
            tmp_path / "custom/hook-config.json"
        )


class TestLoadHookConfig:
    def test_missing_file_returns_default(self, tmp_path: Path):
        from hook_config_schema import default_hook_config, load_hook_config

        loaded = load_hook_config(tmp_path, "cursor")
        assert loaded == default_hook_config()

    def test_reads_valid_file(self, tmp_path: Path):
        from hook_config_schema import load_hook_config

        target = tmp_path / "skill-config/lulu-dev-workflow/hook-config.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"version": 1, "rwGuard": {"enable": False}}),
            encoding="utf-8",
        )
        loaded = load_hook_config(tmp_path, "cursor")
        assert loaded["rwGuard"]["enable"] is False


class TestEnsureHookConfig:
    def test_creates_default_when_missing(self, tmp_path: Path):
        from hook_config_schema import default_hook_config, ensure_hook_config

        target, created = ensure_hook_config(tmp_path, platform="cursor")
        assert created is True
        assert target.exists()
        written = json.loads(target.read_text(encoding="utf-8"))
        assert written == default_hook_config()

    def test_does_not_overwrite_existing(self, tmp_path: Path):
        from hook_config_schema import ensure_hook_config

        target = tmp_path / "skill-config/lulu-dev-workflow/hook-config.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"version": 1, "rwGuard": {"enable": False}}),
            encoding="utf-8",
        )
        path, created = ensure_hook_config(tmp_path, platform="cursor")
        assert created is False
        assert path == target
        assert json.loads(target.read_text(encoding="utf-8"))["rwGuard"]["enable"] is False


class TestResolveRwGuard:
    def test_expands_platform_in_defaults(self, tmp_path: Path):
        from hook_config_schema import resolve_rw_guard

        resolved = resolve_rw_guard(tmp_path, "product-plan", platform="cursor")
        assert resolved["enable"] is True
        assert resolved["readDirs"] == ["."]
        assert resolved["writeDirs"] == [".cache/cursor/lulu-dev-workflow"]

    def test_tech_code_allows_project_root_writes(self, tmp_path: Path):
        from hook_config_schema import resolve_rw_guard

        resolved = resolve_rw_guard(tmp_path, "tech-code", platform="copilot")
        assert resolved["writeDirs"] == ["."]

    def test_stage_enable_override(self, tmp_path: Path):
        from hook_config_schema import ensure_hook_config, resolve_rw_guard

        target, _ = ensure_hook_config(tmp_path, platform="cursor")
        payload = json.loads(target.read_text(encoding="utf-8"))
        payload["rwGuard"]["stages"]["product-plan"] = {"enable": False}
        target.write_text(json.dumps(payload), encoding="utf-8")
        resolved = resolve_rw_guard(tmp_path, "product-plan", platform="cursor")
        assert resolved["enable"] is False
