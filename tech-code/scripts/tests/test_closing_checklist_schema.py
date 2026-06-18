#!/usr/bin/env python3
"""Tests for closing_checklist_schema.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tc_closing_checklist_schema import write_passed, validate_complete  # noqa: E402


def _evidence() -> dict:
    return {
        "task_count": 2,
        "commit_ref_count": 2,
        "tasks_done_count": 2,
        "test_passed": True,
        "git_clean": True,
        "updated_at": "2024-01-01T00:00:00Z",
    }


def test_write_passed_missing_key(tmp_path: Path):
    evidence = _evidence()
    del evidence["git_clean"]
    with pytest.raises(ValueError, match="evidence missing required keys"):
        write_passed(tmp_path / "closing-checklist.md", evidence)


def test_write_passed_and_validate_complete(tmp_path: Path):
    path = tmp_path / "closing-checklist.md"
    write_passed(path, _evidence())
    content = path.read_text(encoding="utf-8")
    assert "- [x] Full test suite re-run (PASS)" in content
    assert "2/2" in content
    validate_complete(path)


def test_validate_complete_unchecked(tmp_path: Path):
    path = tmp_path / "closing-checklist.md"
    path.write_text("- [ ] item\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unchecked items"):
        validate_complete(path)
