#!/usr/bin/env python3
"""Tests for platform_schema.py."""

from __future__ import annotations

import os

import pytest

from platform_schema import (
    PlatformDetectionError,
    detect_platform,
    resolve_platform_context,
    resolve_skill_root,
)


def test_detect_platform_override():
    assert detect_platform(override="copilot") == "copilot"
    assert detect_platform(override="claude") == "claude"


def test_detect_platform_claude_code(monkeypatch):
    monkeypatch.delenv("LULU_PLATFORM", raising=False)
    monkeypatch.delenv("COPILOT_AGENT", raising=False)
    monkeypatch.delenv("VSCODE_TARGET_SESSION_LOG", raising=False)
    monkeypatch.delenv("CURSOR_AGENT", raising=False)
    monkeypatch.setenv("CLAUDE_CODE", "1")
    assert detect_platform() == "claude"


def test_detect_platform_lulu_platform(monkeypatch):
    monkeypatch.setenv("LULU_PLATFORM", "copilot")
    monkeypatch.delenv("COPILOT_AGENT", raising=False)
    monkeypatch.delenv("CURSOR_AGENT", raising=False)
    assert detect_platform() == "copilot"


def test_detect_platform_copilot_agent(monkeypatch):
    monkeypatch.delenv("LULU_PLATFORM", raising=False)
    monkeypatch.setenv("COPILOT_AGENT", "1")
    monkeypatch.delenv("CURSOR_AGENT", raising=False)
    assert detect_platform() == "copilot"


def test_detect_platform_vscode_session_log(monkeypatch):
    monkeypatch.delenv("LULU_PLATFORM", raising=False)
    monkeypatch.delenv("COPILOT_AGENT", raising=False)
    monkeypatch.setenv("VSCODE_TARGET_SESSION_LOG", "/tmp/session.log")
    assert detect_platform() == "copilot"


def test_detect_platform_cursor_agent(monkeypatch):
    monkeypatch.delenv("LULU_PLATFORM", raising=False)
    monkeypatch.delenv("COPILOT_AGENT", raising=False)
    monkeypatch.delenv("VSCODE_TARGET_SESSION_LOG", raising=False)
    monkeypatch.setenv("CURSOR_AGENT", "1")
    assert detect_platform() == "cursor"


def test_detect_platform_strict_raises(monkeypatch):
    for key in (
        "LULU_PLATFORM",
        "COPILOT_AGENT",
        "CURSOR_AGENT",
        "VSCODE_TARGET_SESSION_LOG",
        "CLAUDE_CODE",
    ):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(PlatformDetectionError):
        detect_platform(strict=True)


def test_detect_platform_non_strict_defaults_cursor(monkeypatch):
    for key in (
        "LULU_PLATFORM",
        "COPILOT_AGENT",
        "CURSOR_AGENT",
        "VSCODE_TARGET_SESSION_LOG",
        "CLAUDE_CODE",
    ):
        monkeypatch.delenv(key, raising=False)
    assert detect_platform(strict=False) == "cursor"


def test_resolve_skill_root(tmp_path):
    script = tmp_path / "lulu-workflow" / "scripts" / "runtime_control.py"
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    assert resolve_skill_root(script_path=script) == (tmp_path / "lulu-workflow").resolve()


def test_resolve_platform_context_defaults_cursor(tmp_path, monkeypatch):
    for key in (
        "LULU_PLATFORM",
        "COPILOT_AGENT",
        "CURSOR_AGENT",
        "VSCODE_TARGET_SESSION_LOG",
        "CLAUDE_CODE",
    ):
        monkeypatch.delenv(key, raising=False)
    script = tmp_path / "skill" / "scripts" / "runtime_control.py"
    script.parent.mkdir(parents=True)
    script.write_text("", encoding="utf-8")
    project_root = tmp_path / "project"
    project_root.mkdir()

    payload = resolve_platform_context(
        project_root=project_root,
        script_path=script,
    )
    assert payload == {
        "platform": "cursor",
        "skill_root": str((tmp_path / "skill").resolve()),
        "workflow_dir": ".cursor/lulu-workflow",
        "cache_dir": ".cache/cursor/lulu-workflow",
    }
