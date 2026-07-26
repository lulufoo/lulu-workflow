#!/usr/bin/env python3
"""chapters_control.py is retired with _chapters.json (archive-3.0)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent.parent / "section"
_CTL = _SECTION / "chapters_control.py"


def test_chapters_control_exits_retired() -> None:
    result = subprocess.run(
        [sys.executable, str(_CTL), "status", "--revision-dir", "/tmp"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "retired" in result.stderr.lower()
    assert "narrative_arc_control" in result.stderr
