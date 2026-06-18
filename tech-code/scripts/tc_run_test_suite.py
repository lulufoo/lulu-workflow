#!/usr/bin/env python3
"""Run the Closing full test suite and append results to closing-test-log.md.

Log format (append-only, aligned with task-runner code-log.md test_run):

    ### <ISO8601> · test_run · PASS|FAIL

    command: <test_command>
    cwd: <worktree_path>/
    exit_code: <int>
    duration_ms: <int>

    ```output
    <merged stdout + stderr>
    ```

CLI (debug):
    python3 run_test_suite.py --project-root ... --worktree ... --log-path ...
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from tc_workflow_common import read_json, resolve_workflow_config_path


@dataclass
class TestResult:
    exit_code: int
    command: str
    duration_ms: int
    passed: bool
    output: str = ""


def resolve_test_command(project_root: Path) -> str:
    """Read tech-code.test_command from workflow-config.json."""
    config_path = resolve_workflow_config_path(project_root)
    if not config_path.exists():
        raise ValueError(f"workflow-config.json not found: {config_path}")
    config = read_json(config_path)
    code_cfg = config.get("tech-code", {})
    command = code_cfg.get("test_command", "")
    if not command or not str(command).strip():
        raise ValueError("test_command not configured in workflow-config.json")
    return str(command).strip()


def format_test_log_entry(
    *,
    timestamp: str,
    passed: bool,
    command: str,
    cwd: Path,
    exit_code: int,
    duration_ms: int,
    output: str,
) -> str:
    status = "PASS" if passed else "FAIL"
    cwd_str = str(cwd.resolve())
    if not cwd_str.endswith("/"):
        cwd_str += "/"
    return (
        f"### {timestamp} · test_run · {status}\n\n"
        f"command: {command}\n"
        f"cwd: {cwd_str}\n"
        f"exit_code: {exit_code}\n"
        f"duration_ms: {duration_ms}\n\n"
        f"```output\n"
        f"{output}\n"
        f"```\n"
    )


def execute_test_command(
    *,
    project_root: Path,
    worktree_path: Path,
    test_command: str | None = None,
) -> TestResult:
    """Run test_command in worktree; return result without writing a log."""
    command = test_command or resolve_test_command(project_root)
    cwd = worktree_path.resolve()
    start = time.monotonic()
    result = subprocess.run(
        command,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    duration_ms = int((time.monotonic() - start) * 1000)
    output = (result.stdout or "") + (result.stderr or "")
    passed = result.returncode == 0
    return TestResult(
        exit_code=result.returncode,
        command=command,
        duration_ms=duration_ms,
        passed=passed,
        output=output,
    )


def run_test_suite(
    *,
    project_root: Path,
    worktree_path: Path,
    log_path: Path,
) -> TestResult:
    """Run tech-code.test_command in worktree; append log entry; return result."""
    test_result = execute_test_command(
        project_root=project_root,
        worktree_path=worktree_path,
    )
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entry = format_test_log_entry(
        timestamp=timestamp,
        passed=test_result.passed,
        command=test_result.command,
        cwd=worktree_path.resolve(),
        exit_code=test_result.exit_code,
        duration_ms=test_result.duration_ms,
        output=test_result.output,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        if log_path.exists() and log_path.stat().st_size > 0:
            handle.write("\n")
        handle.write(entry)
    return test_result


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Run Closing full test suite")
    parser.add_argument("--project-root", required=True, help="Absolute path to project root")
    parser.add_argument("--worktree", required=True, help="Absolute path to primary worktree")
    parser.add_argument("--log-path", required=True, help="Absolute path to closing-test-log.md")
    args = parser.parse_args()

    try:
        test_result = run_test_suite(
            project_root=Path(args.project_root).resolve(),
            worktree_path=Path(args.worktree).resolve(),
            log_path=Path(args.log_path).resolve(),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = {
        "exit_code": test_result.exit_code,
        "command": test_result.command,
        "duration_ms": test_result.duration_ms,
        "passed": test_result.passed,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if test_result.passed else 1


if __name__ == "__main__":
    sys.exit(_cli())
