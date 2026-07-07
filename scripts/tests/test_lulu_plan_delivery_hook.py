"""AC-4: lulu-plan/SKILL.md delivery hook — feature-only internal switch before deliver."""

from __future__ import annotations

from pathlib import Path

_LULU_PLAN_SKILL = Path(__file__).resolve().parents[2] / "lulu-plan" / "SKILL.md"


def test_lulu_plan_has_delivery_hook_section():
    content = _LULU_PLAN_SKILL.read_text(encoding="utf-8")
    assert "## Delivery hook" in content


def test_lulu_plan_delivery_hook_feature_only():
    content = _LULU_PLAN_SKILL.read_text(encoding="utf-8")
    assert "feature" in content.lower()
    assert "topic" in content.lower()
    assert "skip" in content.lower()


def test_lulu_plan_delivery_hook_insertion_point():
    content = _LULU_PLAN_SKILL.read_text(encoding="utf-8")
    assert "ReadyForDelivery Rules" in content
    assert "step 3" in content.lower() or "步骤 3" in content
    assert "$SESSION_CONTROL deliver" in content


def test_lulu_plan_delivery_hook_command():
    content = _LULU_PLAN_SKILL.read_text(encoding="utf-8")
    assert "set-execution-mode" in content
    assert '--cycle-id "$CYCLE_ID"' in content
    assert "--mode autonomous" in content
    assert "--internal" in content


def test_lulu_plan_delivery_hook_success_path():
    content = _LULU_PLAN_SKILL.read_text(encoding="utf-8")
    assert "cycles.json" in content
    assert "execution_mode" in content
    assert "autonomous" in content


def test_lulu_plan_delivery_hook_blocking_on_failure():
    content = _LULU_PLAN_SKILL.read_text(encoding="utf-8")
    assert "Blocking" in content
    assert "deliver" in content.lower()
    assert "handoff" in content.lower()
    assert "stderr" in content.lower() or "non-zero" in content.lower()
