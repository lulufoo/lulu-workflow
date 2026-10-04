#!/usr/bin/env python3
"""Tests for host project-root resolution (cwd)."""

from __future__ import annotations

from pathlib import Path

import pytest

from project_root import ProjectRootMismatch, resolve_host_project_root


def test_omitted_uses_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert resolve_host_project_root(None) == tmp_path.resolve()


def test_matching_path_ok(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert resolve_host_project_root(tmp_path) == tmp_path.resolve()
    assert resolve_host_project_root(str(tmp_path)) == tmp_path.resolve()
    assert resolve_host_project_root(".") == tmp_path.resolve()


def test_mismatch_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(ProjectRootMismatch, match="must equal process cwd"):
        resolve_host_project_root(other)
