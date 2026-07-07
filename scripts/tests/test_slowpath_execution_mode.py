"""AC-1: _slowpath.md must not ask for execution mode; new cycles start guided."""

from __future__ import annotations

from pathlib import Path

_SLOWPATH = Path(__file__).resolve().parents[2] / "_slowpath.md"


def test_slowpath_does_not_ask_execution_mode():
    content = _SLOWPATH.read_text(encoding="utf-8")
    assert "Execution mode:" not in content
    assert "(1) guided" not in content
    assert "(2) autonomous" not in content


def test_slowpath_start_examples_omit_mode_flag():
    content = _SLOWPATH.read_text(encoding="utf-8")
    assert '--mode "' not in content
    assert "--mode '" not in content


def test_slowpath_new_cycles_fixed_guided():
    content = _SLOWPATH.read_text(encoding="utf-8")
    assert "guided" in content
    assert "new cycles start with `$EXECUTION_MODE ← guided`" in content
