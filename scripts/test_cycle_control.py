#!/usr/bin/env python3
"""Tests for cycle_control.py CLI."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent
_CYCLE_CONTROL = _SCRIPTS / "cycle_control.py"
_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}
_CYCLE_ID_RE = re.compile(r"^(feature|topic)-\d{14}-[0-9a-f]{8}$")


def _run(*args: str, env=None):
    cmd = [sys.executable, str(_CYCLE_CONTROL), *args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env or _ENV_COPILOT)


class TestCycleControlStart:
    def _cache_dir(self, tmp_path: Path) -> Path:
        return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"

    def test_start_exit_zero(self, tmp_path):
        result = _run(
            "--project-root", str(tmp_path),
            "start", "--name", "test-feature",
        )
        assert result.returncode == 0, result.stderr

    def test_start_stdout_is_cycle_id(self, tmp_path):
        result = _run(
            "--project-root", str(tmp_path),
            "start", "--name", "test-feature",
        )
        last = result.stdout.strip().splitlines()[-1]
        assert _CYCLE_ID_RE.match(last), f"Not a cycle_id: {last!r}"

    def test_start_writes_cycles_json(self, tmp_path):
        result = _run(
            "--project-root", str(tmp_path),
            "start", "--name", "my-feature", "--mode", "autonomous",
        )
        fid = result.stdout.strip().splitlines()[-1]
        data = json.loads((self._cache_dir(tmp_path) / "cycles.json").read_text())
        assert data[fid] == {"name": "my-feature", "execution_mode": "autonomous"}

    def test_start_invalid_project_root(self):
        result = _run(
            "--project-root", "/nonexistent/path/xyz",
            "start", "--name", "test",
        )
        assert result.returncode != 0


class TestCycleControlArchive:
    def _cache_dir(self, tmp_path: Path) -> Path:
        return tmp_path / ".cache" / "copilot" / "lulu-dev-workflow"

    def test_archive_nothing_to_prune(self, tmp_path):
        cache = self._cache_dir(tmp_path)
        cache.mkdir(parents=True)
        (cache / "cycles.json").write_text(json.dumps({"feature-20260101000000-11111111": {"name": "a", "execution_mode": "guided"}}))
        result = _run("--project-root", str(tmp_path), "archive", "--keep", "5")
        assert result.returncode == 0
        assert "Nothing to prune" in result.stdout


class TestCycleControlResolveConfigPath:
    def test_resolve_config_path_exit_zero(self, tmp_path):
        result = _run(
            "--project-root", str(tmp_path),
            "--platform", "cursor",
            "resolve-config-path",
        )
        assert result.returncode == 0
        assert "workflow-config.json" in result.stdout


class TestCycleControlList:
    def test_list_empty(self, tmp_path):
        result = _run("--project-root", str(tmp_path), "list")
        assert result.returncode == 0
        assert "Cycles:" in result.stdout
        assert "(no cycles)" in result.stdout

    def test_list_shows_entries(self, tmp_path):
        _run("--project-root", str(tmp_path), "start", "--name", "alpha", "--type", "topic")
        _run("--project-root", str(tmp_path), "start", "--name", "beta", "--mode", "autonomous")
        result = _run("--project-root", str(tmp_path), "list")
        assert result.returncode == 0
        assert "[topic]" in result.stdout
        assert "alpha" in result.stdout
        assert "[feature]" in result.stdout
        assert "beta [autonomous]" in result.stdout


class TestCycleControlInfo:
    def test_info_json(self, tmp_path):
        start = _run("--project-root", str(tmp_path), "start", "--name", "feat", "--mode", "guided")
        cycle_id = start.stdout.strip().splitlines()[-1]
        result = _run("--project-root", str(tmp_path), "info", "--cycle-id", cycle_id)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["cycle_id"] == cycle_id
        assert data["name"] == "feat"
        assert data["execution_mode"] == "guided"
        assert data["cycle_type"] == "feature"

    def test_info_missing_cycle(self, tmp_path):
        result = _run(
            "--project-root", str(tmp_path),
            "info", "--cycle-id", "feature-20990101000000-00000000",
        )
        assert result.returncode != 0


class TestCycleControlValidate:
    def test_validate_ok(self, tmp_path):
        start = _run("--project-root", str(tmp_path), "start", "--name", "feat")
        cycle_id = start.stdout.strip().splitlines()[-1]
        result = _run("--project-root", str(tmp_path), "validate", "--cycle-id", cycle_id)
        assert result.returncode == 0

    def test_validate_missing_index(self, tmp_path):
        result = _run(
            "--project-root", str(tmp_path),
            "validate", "--cycle-id", "feature-20990101000000-00000000",
        )
        assert result.returncode != 0
