#!/usr/bin/env python3
"""Tests for eval/scripts/codebase_sot.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from codebase_sot import (  # noqa: E402
    CodebaseSotError,
    resolve_codebase_ref,
    resolve_root,
    validate_strategy,
)


class TestResolveRoot:
    def test_dot_means_project_root(self, tmp_path: Path):
        assert resolve_root(".", project_root=tmp_path) == tmp_path.resolve()

    def test_absolute_path(self, tmp_path: Path):
        sub = tmp_path / "repo"
        sub.mkdir()
        assert resolve_root(sub.as_posix(), project_root=tmp_path) == sub.resolve()

    def test_relative_path_under_project(self, tmp_path: Path):
        sub = tmp_path / "pkg"
        sub.mkdir()
        assert resolve_root("pkg", project_root=tmp_path) == sub.resolve()

    def test_missing_root_raises(self, tmp_path: Path):
        with pytest.raises(CodebaseSotError, match="root not found"):
            resolve_root("/no/such/dir", project_root=tmp_path)


class TestValidateStrategy:
    def test_all_ok(self):
        validate_strategy("all")

    def test_unknown_raises(self):
        with pytest.raises(CodebaseSotError, match="unsupported strategy"):
            validate_strategy("glob:**")


class TestResolveCodebaseRef:
    def test_default_ref(self, tmp_path: Path):
        root, strategy = resolve_codebase_ref(
            {"root": ".", "strategy": "all"},
            project_root=tmp_path,
        )
        assert root == tmp_path.resolve()
        assert strategy == "all"
