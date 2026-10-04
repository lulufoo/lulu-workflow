#!/usr/bin/env python3
"""Tests for run_test_suite.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tc_run_test_suite import run_test_suite  # noqa: E402

_SCRIPT = Path(__file__).resolve().parents[1] / "tc_run_test_suite.py"


def _write_config(project_root: Path, test_command: str, checkout_name: str = "project") -> None:
    config_dir = project_root / ".cursor" / "lulu-workflow"
    config_dir.mkdir(parents=True)
    config_dir.joinpath("workflow-config.json").write_text(
        json.dumps({"lulu-exec": {"test_commands": {checkout_name: test_command}}}),
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

    monkeypatch.setattr("tc_run_test_suite.subprocess.run", _run)
    result = run_test_suite(
        project_root=project_root,
        worktree_path=worktree,
        log_path=log_path,
        checkout_name="project",
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

    monkeypatch.setattr("tc_run_test_suite.subprocess.run", _run)
    result = run_test_suite(
        project_root=project_root,
        worktree_path=worktree,
        log_path=log_path,
        checkout_name="project",
    )
    assert result.passed is False
    log_content = log_path.read_text(encoding="utf-8")
    assert "FAIL" in log_content
    assert "fail" in log_content


def test_empty_test_command_skips(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "project"
    project_root.mkdir()
    worktree = tmp_path / "wt"
    worktree.mkdir()
    log_path = tmp_path / "log.md"
    _write_config(project_root, "")

    def _run(*_args, **_kwargs):
        raise AssertionError("empty test command must not invoke subprocess")

    monkeypatch.setattr("tc_run_test_suite.subprocess.run", _run)
    result = run_test_suite(
        project_root=project_root,
        worktree_path=worktree,
        log_path=log_path,
        checkout_name="project",
    )
    assert result.skipped is True
    assert result.passed is True
    assert "SKIP" in log_path.read_text(encoding="utf-8")


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
            "--checkout-name",
            "project",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["passed"] is True
