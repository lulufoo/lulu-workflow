#!/usr/bin/env python3
"""Tests for git_ops.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from git_ops import (  # noqa: E402
    is_worktree,
    normalize_repo_path,
    status_clean,
    validate_worktrees,
    validate_worktrees_clean,
)

_SCRIPT = Path(__file__).resolve().parent / "git_ops.py"


def test_normalize_repo_path():
    assert normalize_repo_path("/foo/bar/") == "/foo/bar"
    assert normalize_repo_path("/foo/bar") == "/foo/bar"


def test_is_worktree_true(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        assert cmd == ["git", "-C", "/wt", "rev-parse", "--is-inside-work-tree"]
        return subprocess.CompletedProcess(cmd, 0, "true\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert is_worktree("/wt/") is True


def test_is_worktree_false(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 1, "false\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert is_worktree("/not-a-repo") is False


def test_status_clean_true(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        assert cmd == ["git", "-C", "/wt", "status", "--porcelain"]
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert status_clean("/wt/") is True


def test_status_clean_false(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 0, " M dirty\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    assert status_clean("/wt") is False


def test_validate_worktrees_missing_path():
    with pytest.raises(ValueError, match="missing worktree_path"):
        validate_worktrees({})


def test_validate_worktrees_invalid_primary(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="primary worktree is not a git worktree"):
        validate_worktrees({"worktree_path": "/bad/"})


def test_validate_worktrees_invalid_extra(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        path = cmd[2]
        if path == "/primary":
            return subprocess.CompletedProcess(cmd, 0, "true\n", "")
        return subprocess.CompletedProcess(cmd, 1, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="extra worktree for 'repo-b' is not a git worktree"):
        validate_worktrees({
            "worktree_path": "/primary/",
            "extra_worktrees": {"repo-b": {"path": "/extra/"}},
        })


def test_validate_worktrees_extra_missing_path(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 0, "true\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="extra_worktree for 'repo-b' missing path"):
        validate_worktrees({
            "worktree_path": "/primary/",
            "extra_worktrees": {"repo-b": {}},
        })


def test_validate_worktrees_success(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 0, "true\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    validate_worktrees({
        "worktree_path": "/primary/",
        "extra_worktrees": {"repo-b": {"path": "/extra/"}},
    })


def test_validate_worktrees_clean_dirty_primary(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        if cmd[3] == "status":
            return subprocess.CompletedProcess(cmd, 0, " M dirty\n", "")
        return subprocess.CompletedProcess(cmd, 0, "true\n", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="primary worktree has uncommitted changes"):
        validate_worktrees_clean({"worktree_path": "/primary/"})


def test_validate_worktrees_clean_dirty_extra(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        path = cmd[2]
        if path == "/extra":
            return subprocess.CompletedProcess(cmd, 0, " M dirty\n", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    with pytest.raises(ValueError, match="extra worktree for 'repo-b' has uncommitted changes"):
        validate_worktrees_clean({
            "worktree_path": "/primary/",
            "extra_worktrees": {"repo-b": {"path": "/extra/"}},
        })


def test_validate_worktrees_clean_success(monkeypatch):
    def _run(cmd, capture_output=True, text=True, check=False):
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("git_ops.subprocess.run", _run)
    validate_worktrees_clean({
        "worktree_path": "/primary/",
        "extra_worktrees": {"repo-b": {"path": "/extra/"}},
    })


def test_cli_help():
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "is-worktree" in result.stdout


def test_cli_is_worktree_success(tmp_path: Path):
    wt = tmp_path / "wt"
    wt.mkdir()
    subprocess.run(["git", "init"], cwd=wt, capture_output=True, check=True)
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "is-worktree", "--path", str(wt)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"ok": True}


def test_cli_is_worktree_failure(tmp_path: Path):
    wt = tmp_path / "wt"
    wt.mkdir()
    result = subprocess.run(
        [sys.executable, str(_SCRIPT), "is-worktree", "--path", str(wt)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "check failed" in result.stderr
