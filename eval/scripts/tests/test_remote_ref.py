#!/usr/bin/env python3
"""Tests for eval/scripts/probe/remote_ref.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remote_ref import UrlFetchError, is_remote_url, read_ref  # noqa: E402


class TestIsRemoteUrl:
    def test_https(self):
        assert is_remote_url("https://example.com/x")

    def test_absolute_path(self):
        assert not is_remote_url("/abs/doc.md")


class TestReadRef:
    def test_reads_absolute_path(self, tmp_path: Path):
        doc = tmp_path / "doc.md"
        doc.write_text("# hello\n", encoding="utf-8")
        assert read_ref(doc.as_posix()) == "# hello\n"

    def test_relative_path_requires_project_root(self, tmp_path: Path):
        doc = tmp_path / "doc.md"
        doc.write_text("x", encoding="utf-8")
        with pytest.raises(UrlFetchError, match="relative path"):
            read_ref("doc.md")

    def test_relative_path_with_project_root(self, tmp_path: Path):
        doc = tmp_path / "doc.md"
        doc.write_text("y", encoding="utf-8")
        assert read_ref("doc.md", project_root=tmp_path) == "y"

    def test_missing_file(self):
        with pytest.raises(UrlFetchError, match="file not found"):
            read_ref("/no/such/file.md")

    def test_unsupported_remote(self):
        with pytest.raises(UrlFetchError, match="unsupported remote"):
            read_ref("https://example.com/plain.txt")
