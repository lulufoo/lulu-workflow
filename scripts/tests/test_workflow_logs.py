#!/usr/bin/env python3
"""Tests for scripts/logs workflow observability."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _write_hook_config(project_root: Path, *, logs_enabled: bool) -> None:
    path = project_root / ".cursor/lulu-dev-workflow/workflow-guard-config.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": 2,
                "logs": {"enabled": logs_enabled},
                "internalPathGuard": {
                    "enable": True,
                    "defaults": {
                        "readDirs": ["."],
                        "writeDirs": [".cache/{platform}/lulu-dev-workflow"],
                    },
                },
                "externalPathGuard": {
                    "enabled": False,
                    "writeAllowExternalPaths": [],
                    "readAllowExternalPaths": [],
                    "sessionAllow": False,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


class TestLogsConfig:
    def test_default_disabled_when_logs_missing(self, tmp_path: Path):
        from logs.logs_config_schema import is_logs_enabled, resolve_logs_dir

        path = tmp_path / ".cursor/lulu-dev-workflow/workflow-guard-config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "version": 2,
                    "internalPathGuard": {"enable": True, "defaults": {}},
                    "externalPathGuard": {},
                }
            ),
            encoding="utf-8",
        )
        assert is_logs_enabled(tmp_path, "cursor") is False
        assert resolve_logs_dir(tmp_path, "cursor") == (
            tmp_path / ".cache/cursor/lulu-dev-workflow/.logs"
        ).resolve()

    def test_enabled_flag(self, tmp_path: Path):
        from logs.logs_config_schema import is_logs_enabled

        _write_hook_config(tmp_path, logs_enabled=True)
        assert is_logs_enabled(tmp_path, "cursor") is True


class TestEmitters:
    def test_emit_io_respects_switch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from logs.workflow_log import emit_io

        monkeypatch.setenv("LULU_PLATFORM", "cursor")
        _write_hook_config(tmp_path, logs_enabled=False)
        emit_io(
            project_root=tmp_path,
            platform="cursor",
            conversation_id="conv-1",
            action="read",
            tool="Read",
            path=str(tmp_path / "a.md"),
        )
        io_log = tmp_path / ".cache/cursor/lulu-dev-workflow/.logs/io.log"
        assert not io_log.exists()

        _write_hook_config(tmp_path, logs_enabled=True)
        emit_io(
            project_root=tmp_path,
            platform="cursor",
            conversation_id="conv-1",
            action="read",
            tool="Read",
            path=str(tmp_path / "a.md"),
        )
        assert io_log.is_file()
        row = json.loads(io_log.read_text(encoding="utf-8").strip().splitlines()[-1])
        assert row["kind"] == "io"
        assert row["conv_id"] == "conv-1"
        assert row["action"] == "read"
        assert row["tool"] == "Read"
        assert "mono_ms" in row

    def test_emit_biz_separate_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from logs.workflow_log import emit_biz, emit_io

        monkeypatch.setenv("LULU_PLATFORM", "cursor")
        _write_hook_config(tmp_path, logs_enabled=True)
        emit_io(
            project_root=tmp_path,
            platform="cursor",
            conversation_id="conv-2",
            action="write",
            tool="Write",
            path=str(tmp_path / "b.md"),
        )
        emit_biz(
            component="narrative-arc",
            event="context.start",
            conversation_id="conv-2",
            project_root=tmp_path,
            platform="cursor",
            detail={"revision_dir": "/tmp/r"},
        )
        log_dir = tmp_path / ".cache/cursor/lulu-dev-workflow/.logs"
        assert (log_dir / "io.log").is_file()
        assert (log_dir / "biz.log").is_file()
        biz = json.loads((log_dir / "biz.log").read_text(encoding="utf-8").strip())
        assert biz["kind"] == "biz"
        assert biz["component"] == "narrative-arc"
        assert biz["event"] == "context.start"
        assert biz["detail"]["revision_dir"] == "/tmp/r"


class TestHookDispatch:
    def test_maybe_log_tool_io(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        from logs.hook_dispatch import maybe_log_tool_io

        monkeypatch.setenv("LULU_PLATFORM", "cursor")
        _write_hook_config(tmp_path, logs_enabled=True)
        maybe_log_tool_io(
            project_root=tmp_path,
            platform="cursor",
            conversation_id="conv-h",
            tool_name="Write",
            path=str(tmp_path / "c.md"),
        )
        maybe_log_tool_io(
            project_root=tmp_path,
            platform="cursor",
            conversation_id="conv-h",
            tool_name="Shell",
            path=str(tmp_path / "c.md"),
        )
        lines = (
            (tmp_path / ".cache/cursor/lulu-dev-workflow/.logs/io.log")
            .read_text(encoding="utf-8")
            .strip()
            .splitlines()
        )
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["tool"] == "Write"
        assert row["action"] == "write"


class TestPlatformDefault:
    def test_default_has_no_logs_config_pointer(self):
        from workflow_config_schema import default_platform_config

        cfg = default_platform_config()
        assert "logsConfig" not in cfg
        assert "hookConfig" not in cfg
        assert "workflowConfig" not in cfg
