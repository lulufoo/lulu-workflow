#!/usr/bin/env python3
"""Tests for scripts/hook/hook_prompt.py."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
_HOOK = _SCRIPTS / "hook"
HOOK_PROMPT = _HOOK / "hook_prompt.py"


def _write_config(tmp_path: Path, *, session_allow: bool) -> None:
    cfg_dir = tmp_path / ".cursor" / "lulu-workflow"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "workflow-guard-config.json").write_text(
        json.dumps(
            {
                "version": 2,
                "internalPathGuard": {"enable": True},
                "externalPathGuard": {
                    "enabled": True,
                    "sessionAllow": session_allow,
                    "readAllowExternalPaths": [],
                    "writeAllowExternalPaths": [],
                },
            }
        ),
        encoding="utf-8",
    )


def test_hook_prompt_writes_session_state(tmp_path):
    _write_config(tmp_path, session_allow=True)
    outside = tmp_path.parent / "prompt-external.txt"
    outside.write_text("x", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(HOOK_PROMPT), "--platform", "cursor"],
        input=json.dumps(
            {
                "conversation_id": "conv-p",
                "prompt": f"please edit {outside}",
                "attachments": [],
            }
        ),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.strip())["continue"] is True
    state = (
        tmp_path
        / ".cache"
        / "cursor"
        / "lulu-workflow"
        / "session-paths"
        / "conv-p.json"
    )
    assert state.exists()
    data = json.loads(state.read_text(encoding="utf-8"))
    assert str(outside.resolve()) in data["paths"]


def test_hook_prompt_noop_when_session_allow_disabled(tmp_path):
    _write_config(tmp_path, session_allow=False)
    outside = tmp_path.parent / "prompt-disabled.txt"
    outside.write_text("x", encoding="utf-8")
    subprocess.run(
        [sys.executable, str(HOOK_PROMPT), "--platform", "cursor"],
        input=json.dumps(
            {
                "conversation_id": "conv-d",
                "prompt": f"edit {outside}",
            }
        ),
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        check=True,
    )
    state = (
        tmp_path
        / ".cache"
        / "cursor"
        / "lulu-workflow"
        / "session-paths"
        / "conv-d.json"
    )
    assert not state.exists()
