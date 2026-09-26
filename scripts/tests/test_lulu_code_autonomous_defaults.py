"""AC-7: lulu-code/SKILL.md — guided interaction points → autonomous defaults; topic exception."""

from __future__ import annotations

from pathlib import Path

_LULU_CODE_SKILL = Path(__file__).resolve().parents[2] / "lulu-code" / "SKILL.md"


def test_lulu_code_no_execution_mode_branching():
    content = _LULU_CODE_SKILL.read_text(encoding="utf-8")
    assert "$EXECUTION_MODE" not in content
    assert "execution_mode:" not in content
    assert "## Execution Mode" not in content
    assert "### Autonomous Overrides" not in content


def test_lulu_code_feature_auto_resume():
    content = _LULU_CODE_SKILL.read_text(encoding="utf-8")
    assert "Feature container" in content
    assert "auto-resume" in content
    assert "do not ask Yes/No" in content


def test_lulu_code_feature_auto_confirm():
    content = _LULU_CODE_SKILL.read_text(encoding="utf-8")
    assert "auto-confirm" in content
    assert "without waiting for user approval" in content


def test_lulu_code_feature_auto_deliver():
    content = _LULU_CODE_SKILL.read_text(encoding="utf-8")
    assert "Auto-complete delivery" in content
    assert "without user confirmation" in content


def test_lulu_code_topic_exception_paths():
    content = _LULU_CODE_SKILL.read_text(encoding="utf-8")
    assert "Topic container" in content
    assert "ask to resume" in content
    assert "Wait for explicit user confirmation before running `confirm-task-ready`" in content
    assert "Wait for explicit user confirmation before running `deliver`" in content


def test_lulu_code_no_guided_wait_in_feature_context():
    content = _LULU_CODE_SKILL.read_text(encoding="utf-8")
    assert "等待用户确认" not in content
    # Recovery HARD-GATE must not require Yes/No for feature-only path
    assert "Show `current_state`, `active_session`, and `current_task` (Executing only); ask to resume." not in content
