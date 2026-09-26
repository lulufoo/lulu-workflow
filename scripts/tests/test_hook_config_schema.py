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
    def test_version_and_guards(self):
        from hook_config_schema import default_hook_config

        cfg = default_hook_config()
        assert cfg["version"] == 2
        assert cfg["logs"]["enabled"] is False
        assert cfg["internalPathGuard"]["enable"] is True
        assert cfg["externalPathGuard"]["enabled"] is False

    def test_returns_deep_copy(self):
        from hook_config_schema import default_hook_config

        first = default_hook_config()
        second = default_hook_config()
        first["internalPathGuard"]["enable"] = False
        assert second["internalPathGuard"]["enable"] is True

    def test_includes_tech_code_stage(self):
        from hook_config_schema import default_hook_config

        stages = default_hook_config()["internalPathGuard"]["stages"]
        assert stages == {
            "lulu-code": {
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

    def test_rejects_legacy_rw_guard_version(self):
        from hook_config_schema import validate_hook_config

        errors = validate_hook_config({"version": 1, "rwGuard": {}})
        assert "version must be 2" in errors
        assert "internalPathGuard must be an object" in errors

    def test_rejects_bad_version(self):
        from hook_config_schema import validate_hook_config

        errors = validate_hook_config({"version": 1, "internalPathGuard": {}})
        assert "version must be 2" in errors


class TestResolveHookConfigPath:
    def test_default_path_when_platform_config_missing(self, tmp_path: Path):
        from hook_config_schema import resolve_hook_config_path

        assert resolve_hook_config_path(tmp_path, "cursor") == (
            tmp_path / ".cursor/lulu-workflow/workflow-guard-config.json"
        )

    def test_leftover_pointer_is_ignored(self, tmp_path: Path):
        from hook_config_schema import resolve_hook_config_path

        cfg_path = tmp_path / ".cursor/lulu-workflow/config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps({"hookConfig": "custom/hook-config.json"}),
            encoding="utf-8",
        )
        assert resolve_hook_config_path(tmp_path, "cursor") == (
            tmp_path / ".cursor/lulu-workflow/workflow-guard-config.json"
        )


class TestLoadHookConfig:
    def test_missing_file_returns_default(self, tmp_path: Path):
        from hook_config_schema import default_hook_config, load_hook_config

        loaded = load_hook_config(tmp_path, "cursor")
        assert loaded == default_hook_config()

    def test_reads_valid_file(self, tmp_path: Path):
        from hook_config_schema import load_hook_config

        target = tmp_path / ".cursor/lulu-workflow/workflow-guard-config.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "version": 2,
                    "internalPathGuard": {"enable": False},
                    "externalPathGuard": {"enabled": True},
                }
            ),
            encoding="utf-8",
        )
        loaded = load_hook_config(tmp_path, "cursor")
        assert loaded["internalPathGuard"]["enable"] is False
        assert loaded["externalPathGuard"]["enabled"] is True

    def test_skill_config_hook_is_not_read(self, tmp_path: Path):
        from hook_config_schema import default_hook_config, is_logs_enabled, load_hook_config

        leftover = tmp_path / "skill-config/lulu-workflow/workflow-guard-config.json"
        leftover.parent.mkdir(parents=True, exist_ok=True)
        leftover.write_text(
            json.dumps(
                {
                    "version": 2,
                    "logs": {"enabled": True},
                    "internalPathGuard": {"enable": True},
                    "externalPathGuard": {},
                }
            ),
            encoding="utf-8",
        )
        assert load_hook_config(tmp_path, "cursor") == default_hook_config()
        assert is_logs_enabled(tmp_path, "cursor") is False

    def test_legacy_rw_guard_falls_back_to_default(self, tmp_path: Path):
        from hook_config_schema import default_hook_config, load_hook_config

        target = tmp_path / ".cursor/lulu-workflow/workflow-guard-config.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps({"version": 1, "rwGuard": {"enable": False}}),
            encoding="utf-8",
        )
        assert load_hook_config(tmp_path, "cursor") == default_hook_config()


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

        target = tmp_path / ".cursor/lulu-workflow/workflow-guard-config.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(
                {
                    "version": 2,
                    "internalPathGuard": {"enable": False},
                }
            ),
            encoding="utf-8",
        )
        path, created = ensure_hook_config(tmp_path, platform="cursor")
        assert created is False
        assert path == target
        assert (
            json.loads(target.read_text(encoding="utf-8"))["internalPathGuard"]["enable"]
            is False
        )


class TestResolveInternalPathGuard:
    def test_expands_platform_in_defaults(self, tmp_path: Path):
        from hook_config_schema import resolve_internal_path_guard

        resolved = resolve_internal_path_guard(tmp_path, "lulu-blueprint", platform="cursor")
        assert resolved["enable"] is True
        assert resolved["readDirs"] == ["."]
        assert resolved["writeDirs"] == [".cache/cursor/lulu-workflow"]

    def test_expands_platform_template(self):
        from hook_config_schema import expand_path_template

        assert expand_path_template(".cache/{platform}/lulu-workflow", "copilot") == (
            ".cache/copilot/lulu-workflow"
        )
        # {platform-skills} is no longer expanded — external paths belong to externalPathGuard
        assert expand_path_template("{platform-skills}", "copilot") == "{platform-skills}"

    def test_tech_code_allows_project_root_writes(self, tmp_path: Path):
        from hook_config_schema import resolve_internal_path_guard

        resolved = resolve_internal_path_guard(tmp_path, "lulu-code", platform="copilot")
        assert resolved["readDirs"] == ["."]
        assert resolved["writeDirs"] == ["."]

    def test_stage_enable_override(self, tmp_path: Path):
        from hook_config_schema import ensure_hook_config, resolve_internal_path_guard

        target, _ = ensure_hook_config(tmp_path, platform="cursor")
        payload = json.loads(target.read_text(encoding="utf-8"))
        payload["internalPathGuard"]["stages"]["lulu-blueprint"] = {"enable": False}
        target.write_text(json.dumps(payload), encoding="utf-8")
        resolved = resolve_internal_path_guard(tmp_path, "lulu-blueprint", platform="cursor")
        assert resolved["enable"] is False


class TestResolveExternalPathGuard:
    def test_defaults_when_missing_block(self, tmp_path: Path):
        from hook_config_schema import ensure_hook_config, resolve_external_path_guard

        ensure_hook_config(tmp_path, platform="cursor")
        resolved = resolve_external_path_guard(tmp_path, platform="cursor")
        assert resolved["enabled"] is False
        assert resolved["sessionAllow"] is False
