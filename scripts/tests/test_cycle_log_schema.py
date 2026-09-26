#!/usr/bin/env python3
"""Tests for cycle_log_schema.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cycle_log_schema import append_cycle_log, log_path  # noqa: E402


class TestAppendCycleLog:
    def test_creates_file_with_expected_format(self, tmp_path: Path):
        cycle_dir = tmp_path / "feature-test"
        append_cycle_log(cycle_dir, "INFO", "lulu-code", "session started")
        content = log_path(cycle_dir).read_text(encoding="utf-8")
        assert content.endswith("\n")
        assert "[INFO] lulu-code session started" in content
        assert content.startswith("20")  # ISO8601 year prefix

    def test_multiple_appends_preserve_order(self, tmp_path: Path):
        cycle_dir = tmp_path / "feature-test"
        append_cycle_log(cycle_dir, "INFO", "lulu-code", "first")
        append_cycle_log(cycle_dir, "ERROR", "lulu-code", "second")
        lines = log_path(cycle_dir).read_text(encoding="utf-8").splitlines()
        assert len(lines) == 2
        assert "first" in lines[0]
        assert "second" in lines[1]

    def test_invalid_level_raises(self, tmp_path: Path):
        with pytest.raises(ValueError, match="invalid log level"):
            append_cycle_log(tmp_path, "DEBUG", "lulu-code", "nope")

    def test_newlines_collapsed_in_message(self, tmp_path: Path):
        cycle_dir = tmp_path / "feature-test"
        append_cycle_log(cycle_dir, "WARN", "lulu-code", "line1\nline2")
        line = log_path(cycle_dir).read_text(encoding="utf-8").strip()
        assert "\n" not in line
        assert "line1 line2" in line

    def test_creates_cycle_dir_if_missing(self, tmp_path: Path):
        cycle_dir = tmp_path / "nested" / "feature-test"
        append_cycle_log(cycle_dir, "INFO", "lulu-plan", "hello")
        assert log_path(cycle_dir).exists()
