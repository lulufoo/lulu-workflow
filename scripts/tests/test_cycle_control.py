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

_SCRIPTS = Path(__file__).resolve().parents[1]
_CYCLE_CONTROL = _SCRIPTS / "cycle_control.py"
_ENV_COPILOT = {**os.environ, "LULU_PLATFORM": "copilot"}
_CYCLE_ID_RE = re.compile(r"^(feature|topic)-\d{14}-[0-9a-f]{8}$")


def _run(*args: str, env=None, cwd=None):
    cmd = [sys.executable, str(_CYCLE_CONTROL), *args]
    arglist = list(args)
    if cwd is None and "--project-root" in arglist:
        raw = arglist[arglist.index("--project-root") + 1]
        if Path(raw).exists():
            cwd = raw
    return subprocess.run(
        cmd, capture_output=True, text=True, env=env or _ENV_COPILOT, cwd=cwd
    )


class TestCycleControlStart:
    def _cache_dir(self, tmp_path: Path) -> Path:
        return tmp_path / ".cache" / "copilot" / "lulu-workflow"

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
            "start", "--name", "my-feature",
        )
        assert result.returncode == 0, result.stderr
        fid = result.stdout.strip().splitlines()[-1]
        data = json.loads((self._cache_dir(tmp_path) / "cycles.json").read_text())
        assert data[fid] == {"name": "my-feature"}

    def test_start_invalid_project_root(self, tmp_path):
        result = _run(
            "--project-root", "/nonexistent/path/xyz",
            "start", "--name", "test",
            cwd=str(tmp_path),
        )
        assert result.returncode != 0
        assert "must equal process cwd" in result.stderr

    def test_start_omit_project_root_uses_cwd(self, tmp_path):
        result = _run("start", "--name", "cwd-host", cwd=str(tmp_path))
        assert result.returncode == 0, result.stderr
        fid = result.stdout.strip().splitlines()[-1]
        data = json.loads((self._cache_dir(tmp_path) / "cycles.json").read_text())
        assert data[fid] == {"name": "cwd-host"}


class TestCycleControlResolveConfigPath:
    def test_resolve_config_path_exit_zero(self, tmp_path):
        result = _run(
            "--project-root", str(tmp_path),
            "--platform", "cursor",
            "resolve-config-path",
        )
        assert result.returncode == 0
        assert ".agents/config/lulu-workflow" in result.stdout


class TestCycleControlMenu:
    def _cache_dir(self, tmp_path: Path) -> Path:
        return tmp_path / ".cache" / "copilot" / "lulu-workflow"

    def _write_cycles(self, tmp_path: Path, data: dict) -> None:
        cache = self._cache_dir(tmp_path)
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "cycles.json").write_text(json.dumps(data), encoding="utf-8")

    def test_menu_empty(self, tmp_path):
        result = _run("--project-root", str(tmp_path), "menu")
        assert result.returncode == 0
        assert "Cycles:" in result.stdout
        assert "(no cycles)" in result.stdout
        assert "N. New topic — type a description to create" in result.stdout
        assert "M. New feature — type a description to create" in result.stdout

    def test_menu_shows_entries(self, tmp_path):
        _run("--project-root", str(tmp_path), "start", "--name", "alpha", "--type", "topic")
        start = _run("--project-root", str(tmp_path), "start", "--name", "beta")
        assert start.returncode == 0, start.stderr
        result = _run("--project-root", str(tmp_path), "menu")
        assert result.returncode == 0
        assert "[topic]" in result.stdout
        assert "alpha" in result.stdout
        assert "[feature]" in result.stdout
        assert "beta" in result.stdout
        assert "N. New topic — type a description to create" in result.stdout
        assert "M. New feature — type a description to create" in result.stdout

    def test_menu_newest_first_and_typed_tokens(self, tmp_path):
        self._write_cycles(
            tmp_path,
            {
                "topic-20260101000000-aaaaaaaa": {"name": "old-topic"},
                "topic-20260601000000-bbbbbbbb": {"name": "new-topic"},
                "feature-20260201000000-cccccccc": {"name": "old-feature"},
                "feature-20260701000000-dddddddd": {"name": "new-feature"},
            },
        )
        result = _run("--project-root", str(tmp_path), "menu")
        assert result.returncode == 0, result.stderr
        lines = [ln for ln in result.stdout.splitlines() if ln.startswith("[")]
        assert [ln.rstrip() for ln in lines] == [
            "[topic]   T1. new-topic",
            "[topic]   T2. old-topic",
            "[feature]   F1. new-feature",
            "[feature]   F2. old-feature",
        ]
        expected = "  \n".join(
            [
                "Cycles:",
                "[topic]   T1. new-topic",
                "[topic]   T2. old-topic",
                "[feature]   F1. new-feature",
                "[feature]   F2. old-feature",
                "N. New topic — type a description to create",
                "M. New feature — type a description to create",
            ]
        )
        assert result.stdout == expected + "\n"

    def test_menu_truncates_to_five_per_type(self, tmp_path):
        data = {}
        for i in range(6):
            data[f"topic-2026010{i+1:02d}000000-{'a'*8}"] = {"name": f"t{i}"}
            data[f"feature-2026020{i+1:02d}000000-{'b'*8}"] = {"name": f"f{i}"}
        self._write_cycles(tmp_path, data)
        result = _run("--project-root", str(tmp_path), "menu")
        assert result.returncode == 0, result.stderr
        lines = [ln for ln in result.stdout.splitlines() if ln.startswith("[")]
        assert len(lines) == 10
        topic_lines = [ln for ln in lines if ln.startswith("[topic]")]
        feature_lines = [ln for ln in lines if ln.startswith("[feature]")]
        assert len(topic_lines) == 5
        assert len(feature_lines) == 5
        assert "t5" in topic_lines[0]
        assert "t0" not in result.stdout
        assert "f5" in feature_lines[0]
        assert "f0" not in result.stdout
        assert lines[0].startswith("[topic]   T1.")
        assert lines[-1].startswith("[feature]   F5.")

    def test_resolve_token_ok(self, tmp_path):
        self._write_cycles(
            tmp_path,
            {
                "topic-20260101000000-aaaaaaaa": {"name": "old-topic"},
                "topic-20260601000000-bbbbbbbb": {"name": "new-topic"},
                "feature-20260201000000-cccccccc": {"name": "old-feature"},
                "feature-20260701000000-dddddddd": {"name": "new-feature"},
            },
        )
        result = _run(
            "--project-root", str(tmp_path), "resolve-token", "--token", "F2"
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "feature-20260201000000-cccccccc"

    def test_resolve_token_case_insensitive(self, tmp_path):
        self._write_cycles(
            tmp_path,
            {"topic-20260601000000-bbbbbbbb": {"name": "new-topic"}},
        )
        result = _run(
            "--project-root", str(tmp_path), "resolve-token", "--token", "t1"
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "topic-20260601000000-bbbbbbbb"

    def test_resolve_token_out_of_range(self, tmp_path):
        self._write_cycles(
            tmp_path,
            {"feature-20260701000000-dddddddd": {"name": "new-feature"}},
        )
        result = _run(
            "--project-root", str(tmp_path), "resolve-token", "--token", "F9"
        )
        assert result.returncode != 0


class TestCycleControlInfo:
    def test_info_json(self, tmp_path):
        start = _run("--project-root", str(tmp_path), "start", "--name", "feat")
        assert start.returncode == 0, start.stderr
        cycle_id = start.stdout.strip().splitlines()[-1]
        result = _run("--project-root", str(tmp_path), "info", "--cycle-id", cycle_id)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["cycle_id"] == cycle_id
        assert data["name"] == "feat"
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


_ENV_BIND = {
    key: value
    for key, value in _ENV_COPILOT.items()
    if key != "LULU_CONVERSATION_ID"
}


class TestCycleControlBindContext:
    def _cache_dir(self, tmp_path: Path) -> Path:
        return tmp_path / ".cache" / "copilot" / "lulu-workflow"

    def test_bind_writes_active_context(self, tmp_path):
        start = _run(
            "--project-root", str(tmp_path), "start", "--name", "feat", env=_ENV_BIND
        )
        assert start.returncode == 0, start.stderr
        cycle_id = start.stdout.strip().splitlines()[-1]
        skill_dir = tmp_path / "skills" / "lulu-plan"
        skill_dir.mkdir(parents=True)
        result = _run(
            "--project-root",
            str(tmp_path),
            "bind-context",
            "--cycle-id",
            cycle_id,
            "--skill-dir",
            str(skill_dir),
            "--conversation-id",
            "conv-new",
            env=_ENV_BIND,
        )
        assert result.returncode == 0, result.stderr
        ctx = json.loads(
            (self._cache_dir(tmp_path) / "active-context.json").read_text(encoding="utf-8")
        )
        assert ctx["conv-new"] == {
            "cycle_id": cycle_id,
            "stage": "lulu-plan",
            "cycle_type": "feature",
        }

    def test_bind_rejects_missing_conversation_id(self, tmp_path):
        start = _run(
            "--project-root", str(tmp_path), "start", "--name", "feat", env=_ENV_BIND
        )
        cycle_id = start.stdout.strip().splitlines()[-1]
        result = _run(
            "--project-root",
            str(tmp_path),
            "bind-context",
            "--cycle-id",
            cycle_id,
            "--skill-dir",
            str(tmp_path / "lulu-plan"),
            env=_ENV_BIND,
        )
        assert result.returncode != 0
        assert not (self._cache_dir(tmp_path) / "active-context.json").exists()

    def test_bind_rejects_missing_cycle(self, tmp_path):
        result = _run(
            "--project-root",
            str(tmp_path),
            "bind-context",
            "--cycle-id",
            "feature-20990101000000-00000000",
            "--skill-dir",
            str(tmp_path / "lulu-plan"),
            "--conversation-id",
            "conv-x",
            env=_ENV_BIND,
        )
        assert result.returncode != 0

    def test_bind_rejects_illegal_stage(self, tmp_path):
        start = _run(
            "--project-root", str(tmp_path), "start", "--name", "feat", env=_ENV_BIND
        )
        cycle_id = start.stdout.strip().splitlines()[-1]
        result = _run(
            "--project-root",
            str(tmp_path),
            "bind-context",
            "--cycle-id",
            cycle_id,
            "--skill-dir",
            str(tmp_path / "landscape"),
            "--conversation-id",
            "conv-x",
            env=_ENV_BIND,
        )
        assert result.returncode != 0
        assert not (self._cache_dir(tmp_path) / "active-context.json").exists()

    def test_bind_then_resolve_session_context(self, tmp_path):
        start = _run(
            "--project-root", str(tmp_path), "start", "--name", "feat", env=_ENV_BIND
        )
        cycle_id = start.stdout.strip().splitlines()[-1]
        skill_dir = tmp_path / "lulu-plan"
        bind = _run(
            "--project-root",
            str(tmp_path),
            "bind-context",
            "--cycle-id",
            cycle_id,
            "--skill-dir",
            str(skill_dir),
            "--conversation-id",
            "conv-restore",
            env=_ENV_BIND,
        )
        assert bind.returncode == 0, bind.stderr
        runtime = Path(__file__).resolve().parents[1] / "runtime_control.py"
        resolve = subprocess.run(
            [
                sys.executable,
                str(runtime),
                "--project-root",
                str(tmp_path),
                "resolve-session-context",
                "--conversation-id",
                "conv-restore",
            ],
            capture_output=True,
            text=True,
            env=_ENV_BIND,
            cwd=str(tmp_path),
        )
        assert resolve.returncode == 0, resolve.stderr
        payload = json.loads(resolve.stdout.strip())
        assert payload["cycle_id"] == cycle_id
        assert payload["stage"] == "lulu-plan"
        assert payload["cycle_type"] == "feature"
