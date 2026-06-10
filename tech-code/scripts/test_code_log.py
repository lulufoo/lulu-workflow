#!/usr/bin/env python3
"""Tests for code_log.py."""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from code_log import append_enter, append_git_commit, append_test_run  # noqa: E402


def test_append_enter_creates_log(tmp_path: Path):
    task_dir = tmp_path / "tasks" / "t1"
    append_enter(task_dir, "WriteTests")
    content = (task_dir / "code-log.md").read_text(encoding="utf-8")
    assert re.search(r"^### .+ · enter · WriteTests$", content, re.MULTILINE)


def test_append_test_run_format(tmp_path: Path):
    task_dir = tmp_path / "tasks" / "t1"
    append_test_run(
        task_dir,
        passed=False,
        command="npm test",
        cwd=tmp_path / "wt",
        exit_code=1,
        duration_ms=42,
        output="FAIL\n",
    )
    content = (task_dir / "code-log.md").read_text(encoding="utf-8")
    assert "test_run · FAIL" in content
    assert "command: npm test" in content
    assert "exit_code: 1" in content
    assert "```output" in content


def test_append_git_commit_initial(tmp_path: Path):
    task_dir = tmp_path / "tasks" / "t1"
    append_git_commit(task_dir, kind="initial", sha="abc123", message="feat(code): t1 test")
    content = (task_dir / "code-log.md").read_text(encoding="utf-8")
    assert "git_commit · initial" in content
    assert "sha: abc123" in content
    assert "message: feat(code): t1 test" in content
