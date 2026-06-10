#!/usr/bin/env python3
"""Tests for run_test_suite.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_test_suite import run_test_suite  # noqa: E402

_SCRIPT = Path(__file__).resolve().parent / "run_test_suite.py"


def _write_config(project_root: Path, test_command: str) -> None:
    config_dir = project_root / "skill-config" / "lulu-dev-workflow"
    config_dir.mkdir(parents=True)
    config_dir.joinpath("workflow-config.json").write_text(
        json.dumps({"tech-code": {"test_command": test_command}}),
        encoding="utf-8",
    )


def test_run_test_suite_pass(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "project"
    project_root.mkdir()
    worktree = tmp_path / "wt"
    worktree.mkdir()
    log_path = tmp_path / "closing-test-log.md"
    _write_config(project_root, "echo hello")

    def _run(cmd, shell, cwd, capture_output, text):
        assert shell is True
        return subprocess.CompletedProcess(cmd, 0, "hello\n", "")

    monkeypatch.setattr("run_test_suite.subprocess.run", _run)
    result = run_test_suite(
        project_root=project_root,
        worktree_path=worktree,
        log_path=log_path,
    )
    assert result.passed is True
    assert result.exit_code == 0
    log_content = log_path.read_text(encoding="utf-8")
    assert "```output" in log_content
    assert "hello" in log_content


def test_run_test_suite_fail(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "project"
    project_root.mkdir()
    worktree = tmp_path / "wt"
    worktree.mkdir()
    log_path = tmp_path / "closing-test-log.md"
    _write_config(project_root, "false")

    def _run(cmd, shell, cwd, capture_output, text):
        return subprocess.CompletedProcess(cmd, 1, "", "fail\n")

    monkeypatch.setattr("run_test_suite.subprocess.run", _run)
    result = run_test_suite(
        project_root=project_root,
        worktree_path=worktree,
        log_path=log_path,
    )
    assert result.passed is False
    log_content = log_path.read_text(encoding="utf-8")
    assert "FAIL" in log_content
    assert "fail" in log_content


def test_empty_test_command_raises(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    _write_config(project_root, "")
    with pytest.raises(ValueError, match="test_command not configured"):
        run_test_suite(
            project_root=project_root,
            worktree_path=tmp_path / "wt",
            log_path=tmp_path / "log.md",
        )


def test_cli_pass(tmp_path: Path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    worktree = tmp_path / "wt"
    worktree.mkdir()
    log_path = tmp_path / "closing-test-log.md"
    _write_config(project_root, "echo ok")
    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--project-root",
            str(project_root),
            "--worktree",
            str(worktree),
            "--log-path",
            str(log_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
