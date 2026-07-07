"""AC-2: _runtime.md defines phase identifier; plan delivery internal switch; no user SET_EXECUTION_MODE."""

from __future__ import annotations

from pathlib import Path

_RUNTIME = Path(__file__).resolve().parents[2] / "_runtime.md"


def test_runtime_defines_execution_mode_as_phase_identifier():
    content = _RUNTIME.read_text(encoding="utf-8")
    assert "stage identifier" in content.lower()
    assert "not user-switchable" in content.lower()


def test_runtime_no_user_set_execution_mode_guidance():
    content = _RUNTIME.read_text(encoding="utf-8")
    assert "user sends `SET_EXECUTION_MODE" not in content
    assert "Change mode:" not in content


def test_runtime_plan_delivery_internal_switch():
    content = _RUNTIME.read_text(encoding="utf-8")
    assert "delivery hook" in content.lower()
    assert "set-execution-mode" in content
    assert "--internal" in content
    assert "execution_mode=autonomous" in content


def test_runtime_set_execution_mode_internal_only():
    content = _RUNTIME.read_text(encoding="utf-8")
    assert "internal only" in content.lower()
    assert "must not send `SET_EXECUTION_MODE`" in content
