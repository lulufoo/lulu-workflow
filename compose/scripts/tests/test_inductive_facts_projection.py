#!/usr/bin/env python3
"""Tests for retired K2 inductive facts projection (K4)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_INDUCTIVE = Path(__file__).resolve().parent.parent / "inductive"
_PROJ = _INDUCTIVE / "inductive_facts_projection.py"

sys.path.insert(0, str(_INDUCTIVE))
import inductive_facts_projection as proj  # noqa: E402


def test_project_cli_returns_retired_error(tmp_path: Path) -> None:
    res = subprocess.run(
        [
            sys.executable,
            str(_PROJ),
            "project",
            "--revision-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 1
    err = res.stderr + res.stdout
    assert "retired" in err.lower()
    assert "do not project" in err.lower() or "discovery loop" in err.lower()


def test_project_cmd_retired_constant() -> None:
    assert "retired" in proj.RETIRED_MSG.lower()
    assert proj.cmd_project(None) == 1
