#!/usr/bin/env python3
"""Tests for commit_ref_schema.py."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from commit_ref_schema import (  # noqa: E402
    load_commit_ref,
    validate_commit_ref,
    validate_session_commit_refs,
    write_commit_ref,
)


def _valid_ref_text(task_id: str = "t1") -> str:
    return (
        f"task_id: {task_id}\n"
        "branch: wt/feat-test\n"
        "initial_commit: abc123\n"
        "final_commit: def456\n"
        "commit_message: \"feat: test\"\n"
        "amended: false\n"
        "recorded_at: 2024-01-01T00:00:00Z\n"
    )


def test_load_commit_ref_valid(tmp_path: Path):
    path = tmp_path / "commit-ref.md"
    path.write_text(_valid_ref_text(), encoding="utf-8")
    data = load_commit_ref(path)
    assert data["task_id"] == "t1"
    assert data["commit_message"] == "feat: test"
    assert data["amended"] is False


def test_load_commit_ref_missing_field(tmp_path: Path):
    path = tmp_path / "commit-ref.md"
    path.write_text("task_id: t1\ninitial_commit: abc\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing required fields"):
        load_commit_ref(path)


def test_validate_commit_ref_task_id_mismatch():
    data = {
        "task_id": "t2",
        "initial_commit": "abc",
        "final_commit": "def",
        "amended": False,
        "recorded_at": "2024-01-01T00:00:00Z",
    }
    with pytest.raises(ValueError, match="task_id mismatch"):
        validate_commit_ref(data, "t1")


def test_validate_session_commit_refs_success(tmp_path: Path):
    session_dir = tmp_path / "s1"
    tasks_dir = session_dir / "tasks" / "t1"
    tasks_dir.mkdir(parents=True)
    (tasks_dir / "commit-ref.md").write_text(_valid_ref_text("t1"), encoding="utf-8")
    tasks = [{"id": "t1", "done": True}]
    validate_session_commit_refs(session_dir, tasks)


def test_validate_session_commit_refs_orphan(tmp_path: Path):
    session_dir = tmp_path / "s1"
    orphan_dir = session_dir / "tasks" / "t9"
    orphan_dir.mkdir(parents=True)
    (orphan_dir / "commit-ref.md").write_text(_valid_ref_text("t9"), encoding="utf-8")
    tasks = [{"id": "t1", "done": True}]
    t1_dir = session_dir / "tasks" / "t1"
    t1_dir.mkdir(parents=True)
    (t1_dir / "commit-ref.md").write_text(_valid_ref_text("t1"), encoding="utf-8")
    with pytest.raises(ValueError, match="orphan commit-ref"):
        validate_session_commit_refs(session_dir, tasks)


def test_write_commit_ref_roundtrip(tmp_path: Path):
    path = tmp_path / "commit-ref.md"
    data = {
        "task_id": "t1",
        "branch": "wt/feat-test",
        "initial_commit": "abc123",
        "final_commit": "abc123",
        "commit_message": "feat(code): t1 test",
        "amended": False,
        "recorded_at": "2024-01-01T00:00:00Z",
    }
    write_commit_ref(path, data)
    loaded = load_commit_ref(path)
    assert loaded["task_id"] == "t1"
    assert loaded["commit_message"] == "feat(code): t1 test"


def test_validate_session_commit_refs_missing(tmp_path: Path):
    session_dir = tmp_path / "s1"
    session_dir.mkdir()
    tasks = [{"id": "t1", "done": True}]
    with pytest.raises(ValueError, match="commit-ref.md not found"):
        validate_session_commit_refs(session_dir, tasks)
