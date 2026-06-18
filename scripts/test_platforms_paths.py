#!/usr/bin/env python3
"""Tests for platforms.paths."""

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from platforms.paths import (  # noqa: E402
    cache_dir,
    gitignore_entry,
    hook_guard_command,
    hooks_config_path,
    workflow_dir,
)


class TestPlatformPaths:
    def test_workflow_dir_cursor(self):
        assert workflow_dir("cursor") == Path(".cursor/lulu-dev-workflow")

    def test_cache_dir_claude(self):
        assert cache_dir("claude") == Path(".cache/claude/lulu-dev-workflow")

    def test_hooks_config_path_copilot(self):
        assert hooks_config_path("copilot") == Path(".github/hooks/hooks.json")

    def test_gitignore_entry_only_cursor_and_claude(self):
        assert gitignore_entry("cursor") == ".cursor"
        assert gitignore_entry("claude") == ".claude"
        assert gitignore_entry("copilot") is None

    def test_hook_guard_command_includes_platform_flag_for_claude(self):
        command = hook_guard_command("claude")
        assert "hook_guard.py" in command
        assert command.endswith("--platform claude")
