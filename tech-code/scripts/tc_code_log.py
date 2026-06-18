#!/usr/bin/env python3
"""Append-only code-log.md helpers for task-level action logs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from tc_run_test_suite import format_test_log_entry


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _log_path(task_output_dir: Path) -> Path:
    return task_output_dir / "code-log.md"


def _ensure_dir(task_output_dir: Path) -> None:
    task_output_dir.mkdir(parents=True, exist_ok=True)


def _append_entry(task_output_dir: Path, entry: str) -> None:
    _ensure_dir(task_output_dir)
    path = _log_path(task_output_dir)
    with path.open("a", encoding="utf-8") as handle:
        if path.exists() and path.stat().st_size > 0:
            handle.write("\n")
        handle.write(entry)


def append_enter(task_output_dir: Path, phase: str) -> None:
    """Append `enter · {phase}` header."""
    entry = f"### {_timestamp()} · enter · {phase}\n"
    _append_entry(task_output_dir, entry)


def append_test_run(
    task_output_dir: Path,
    *,
    passed: bool,
    command: str,
    cwd: Path,
    exit_code: int,
    duration_ms: int,
    output: str,
) -> None:
    """Append test_run log entry (authoritative format from tc_run_test_suite)."""
    entry = format_test_log_entry(
        timestamp=_timestamp(),
        passed=passed,
        command=command,
        cwd=cwd,
        exit_code=exit_code,
        duration_ms=duration_ms,
        output=output,
    )
    _append_entry(task_output_dir, entry)


def append_git_commit(
    task_output_dir: Path,
    *,
    kind: str,
    sha: str,
    message: str,
) -> None:
    """Append git_commit · initial|amend with sha and message body."""
    if kind not in ("initial", "amend"):
        raise ValueError(f"git_commit kind must be initial or amend, got {kind!r}")
    entry = (
        f"### {_timestamp()} · git_commit · {kind}\n\n"
        f"sha: {sha}\n"
        f"message: {message}\n"
    )
    _append_entry(task_output_dir, entry)
