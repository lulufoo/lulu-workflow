#!/usr/bin/env python3
"""Tests for fidelity_control gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_FIDELITY = Path(__file__).resolve().parents[1]
_CTL = _FIDELITY / "fidelity_control.py"


def _run(revision: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_CTL), "--revision-dir", str(revision), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_require_fails_without_state(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    result = _run(rev, "require-for-derive")
    assert result.returncode != 0
    assert "fidelity gate missing" in result.stderr


def test_mark_passed_opens_gate(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    assert _run(rev, "init", "--intake", "atomize").returncode == 0
    assert _run(rev, "mark-passed").returncode == 0
    result = _run(rev, "require-for-derive")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"


def test_mark_skipped_is_not_available(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    result = _run(rev, "mark-skipped", "--reason", "unit-import")
    assert result.returncode != 0
    assert "invalid choice" in result.stderr
