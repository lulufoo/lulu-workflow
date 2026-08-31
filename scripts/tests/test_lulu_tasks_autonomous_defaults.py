"""AC-5: lulu-tasks/SKILL.md — delete Execution Mode; promote Overrides to default rules."""

from __future__ import annotations

from pathlib import Path

_LULU_TASKS_SKILL = Path(__file__).resolve().parents[2] / "lulu-tasks" / "SKILL.md"


def test_lulu_tasks_no_execution_mode_section():
    content = _LULU_TASKS_SKILL.read_text(encoding="utf-8")
    assert "## Execution Mode: Apply" not in content
    assert "### Autonomous Overrides" not in content


def test_lulu_tasks_no_execution_mode_branching():
    content = _LULU_TASKS_SKILL.read_text(encoding="utf-8")
    assert "$EXECUTION_MODE" not in content
    assert "execution_mode:" not in content
    assert "guided mode" not in content.lower()


def test_lulu_tasks_feature_auto_tech_ref():
    content = _LULU_TASKS_SKILL.read_text(encoding="utf-8")
    assert "Feature container" in content
    assert "Auto-parse" in content or "auto-parse" in content
    assert "tech-doc.md" in content


def test_lulu_tasks_topic_manual_confirm_paths():
    content = _LULU_TASKS_SKILL.read_text(encoding="utf-8")
    assert "Topic container" in content
    assert "Wait for user to confirm the task breakdown" in content
    assert "Proceed to Evaluating?" in content
    assert "Wait for explicit delivery confirmation" in content


def test_lulu_tasks_feature_autonomous_defaults():
    content = _LULU_TASKS_SKILL.read_text(encoding="utf-8")
    assert "Proceed to task.md generation without asking" in content
    assert "Write `workflow-state.md: Evaluating` immediately" in content
    assert "default decision **Fix**" in content
    assert "immediately start `lulu-code`" in content
    assert "auto-chain" not in content


def test_lulu_tasks_sot_askquestion_preserved():
    content = _LULU_TASKS_SKILL.read_text(encoding="utf-8")
    assert "SOT issues always require AskQuestion" in content


def test_lulu_tasks_reads_skill_templates_not_fetch_cli():
    content = _LULU_TASKS_SKILL.read_text(encoding="utf-8")
    assert "$FETCH_TEMPLATE" not in content
    assert "templates/31-work-order-tasklist-template.md" in content
    assert "templates/30-work-order-task-template.md" in content
    assert "templates/34-tech-doc-admission-framework.md" in content


def test_eval_runner_reads_skill_templates_not_fetch_cli():
    path = Path(__file__).resolve().parents[2] / "lulu-tasks" / "eval-runner" / "SKILL.md"
    content = path.read_text(encoding="utf-8")
    assert "$FETCH_TEMPLATE --section" not in content
    assert "{framework_tda}" in content
    assert "34-tech-doc-admission-framework.md" in content
