#!/usr/bin/env python3
"""Tests for scripts/hook/session_paths.py and external_path_guard.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_HOOK = _SCRIPTS / "hook"
if str(_HOOK) not in sys.path:
    sys.path.insert(0, str(_HOOK))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from external_path_guard import check_external_read, matches_allowlist  # noqa: E402
from session_paths import (  # noqa: E402
    add_session_paths,
    collect_eligible_paths,
    is_session_allowed,
)


def test_collect_and_session_allow_directory_prefix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    outside_dir = tmp_path.parent / "ext-session-dir"
    outside_dir.mkdir(exist_ok=True)
    child = outside_dir / "nested" / "a.txt"
    eligible = collect_eligible_paths(
        prompt=f"edit {outside_dir}",
        attachments=[],
        workspace_root=tmp_path.resolve(),
    )
    assert str(outside_dir.resolve()) in eligible
    add_session_paths("conv-1", eligible, platform="cursor")
    assert is_session_allowed(str(child), "conv-1", platform="cursor")


def test_matches_allowlist_tilde(tmp_path):
    cursor = str(Path("~/.cursor").expanduser())
    assert matches_allowlist(f"{cursor}/skills/x.md", ["~/.cursor/"]) is True
    assert matches_allowlist("/tmp/nope.md", ["~/.cursor/"]) is False


def test_check_external_read_session_allow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    target = tmp_path.parent / "sess-read.txt"
    add_session_paths("conv-2", [str(target)], platform="cursor")
    assert (
        check_external_read(
            str(target),
            read_allow=[],
            session_allow=True,
            session_id="conv-2",
            platform="cursor",
        )
        is None
    )
    assert (
        check_external_read(
            "/tmp/other-denied.md",
            read_allow=[],
            session_allow=True,
            session_id="conv-2",
            platform="cursor",
        )
        == "/tmp/other-denied.md"
    )
