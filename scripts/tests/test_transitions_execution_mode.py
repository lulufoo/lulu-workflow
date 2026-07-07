"""AC-3: _transitions.md plan delivery switch, auto-chain, and Autonomous Overrides refs."""

from __future__ import annotations

from pathlib import Path

_TRANSITIONS = Path(__file__).resolve().parents[2] / "_transitions.md"


def test_transitions_plan_delivery_switch_handoff_sequence():
    content = _TRANSITIONS.read_text(encoding="utf-8")
    assert "Delivered" in content
    assert "set-execution-mode" in content
    assert "--internal" in content
    assert "execution_mode=autonomous" in content
    assert "handoff" in content.lower()


def test_transitions_auto_chain_trigger_conditions():
    content = _TRANSITIONS.read_text(encoding="utf-8")
    assert 'execution_mode == "autonomous"' in content or "execution_mode==autonomous" in content
    assert "cycle_type" in content
    assert "feature" in content
    assert "cycles.json" in content


def test_transitions_no_lulu_plan_autonomous_overrides_reference():
    content = _TRANSITIONS.read_text(encoding="utf-8")
    assert "lulu-plan/SKILL.md" not in content


def test_transitions_no_lulu_code_autonomous_overrides_reference():
    content = _TRANSITIONS.read_text(encoding="utf-8")
    assert "lulu-code/SKILL.md" not in content


def test_transitions_autonomous_overrides_only_lulu_tasks():
    content = _TRANSITIONS.read_text(encoding="utf-8")
    assert "Autonomous Overrides" in content
    assert "lulu-tasks/SKILL.md" in content
