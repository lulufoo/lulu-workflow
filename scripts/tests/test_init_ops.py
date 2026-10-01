#!/usr/bin/env python3
"""Tests for init_ops hook registration."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from platforms.init.claude import register_claude_hook  # noqa: E402
from platforms.init.cursor import register_cursor_hook  # noqa: E402
from platforms.paths import CLAUDE_PRE_TOOL_USE_MATCHER, hook_guard_command  # noqa: E402

_CLAUDE_HOOK_COMMAND = hook_guard_command("claude")
_CLAUDE_PRE_TOOL_USE_MATCHER = CLAUDE_PRE_TOOL_USE_MATCHER


class TestRegisterCursorHook:
    def test_writes_pre_tool_use_entry(self, tmp_path):
        register_cursor_hook(tmp_path)
        payload = json.loads((tmp_path / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
        entries = payload["hooks"]["preToolUse"]
        assert any("lulu-workflow" in e.get("command", "") for e in entries)
        assert any(e.get("matcher") == "Write|Edit|Read|Shell" for e in entries)

    def test_writes_before_submit_prompt_entry(self, tmp_path):
        register_cursor_hook(tmp_path)
        payload = json.loads((tmp_path / ".cursor" / "hooks.json").read_text(encoding="utf-8"))
        prompts = payload["hooks"]["beforeSubmitPrompt"]
        assert any("hook_prompt.py" in e.get("command", "") for e in prompts)


class TestRegisterClaudeHook:
    def test_writes_nested_pre_tool_use(self, tmp_path):
        register_claude_hook(tmp_path)
        payload = json.loads((tmp_path / ".claude" / "settings.json").read_text(encoding="utf-8"))
        entries = payload["hooks"]["PreToolUse"]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["matcher"] == _CLAUDE_PRE_TOOL_USE_MATCHER
        assert entry["hooks"][0]["command"] == _CLAUDE_HOOK_COMMAND
        assert entry["hooks"][0]["type"] == "command"

    def test_replaces_existing_lulu_entry(self, tmp_path):
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": _CLAUDE_PRE_TOOL_USE_MATCHER,
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "python3 old/lulu-workflow/hook.py",
                                    }
                                ],
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        register_claude_hook(tmp_path)
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        commands = [
            h.get("command", "")
            for entry in payload["hooks"]["PreToolUse"]
            for h in entry.get("hooks", [])
        ]
        assert commands == [_CLAUDE_HOOK_COMMAND]

    def test_preserves_unrelated_pre_tool_use_entries(self, tmp_path):
        settings_path = tmp_path / ".claude" / "settings.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "Bash",
                                "hooks": [
                                    {"type": "command", "command": "python3 other/hook.py"}
                                ],
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        register_claude_hook(tmp_path)
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        matchers = [entry.get("matcher") for entry in payload["hooks"]["PreToolUse"]]
        assert "Bash" in matchers
        assert _CLAUDE_PRE_TOOL_USE_MATCHER in matchers


class TestRunInitProjectPlatformBranch:
    def test_claude_registers_settings_json(self, tmp_path):
        from init_ops import run_init_project

        with patch("init_ops.SUB_WORKFLOWS", []):
            rc = run_init_project(tmp_path, "claude")
        assert rc == 0
        assert (tmp_path / ".claude" / "settings.json").is_file()

    def test_copilot_registers_github_hooks(self, tmp_path):
        from init_ops import run_init_project

        with patch("init_ops.SUB_WORKFLOWS", []):
            rc = run_init_project(tmp_path, "copilot")
        assert rc == 0
        assert (tmp_path / ".github" / "hooks" / "hooks.json").is_file()

    def test_does_not_create_pointer_config(self, tmp_path):
        from init_ops import run_init_project

        with patch("init_ops.SUB_WORKFLOWS", []):
            rc = run_init_project(tmp_path, "cursor")
        assert rc == 0
        root = tmp_path / ".agents/config/lulu-workflow"
        assert not (root / "config.json").exists()
        assert (root / "workflow-guard-config.json").is_file()
        assert (root / "manifest.json").is_file()
        assert (root / "stages/lulu-exec.json").is_file()
        assert not (root / "stages/lulu-tasks.json").exists()

    def test_does_not_overwrite_existing_stage_config(self, tmp_path):
        from init_ops import run_init_project

        dest = tmp_path / ".cursor/lulu-workflow/stages/lulu-exec.json"
        dest.parent.mkdir(parents=True)
        dest.write_text('{"test_command": "KEEP"}\n', encoding="utf-8")
        with patch("init_ops.SUB_WORKFLOWS", []):
            rc = run_init_project(tmp_path, "cursor")
        assert rc == 0
        assert dest.read_text(encoding="utf-8") == '{"test_command": "KEEP"}\n'
