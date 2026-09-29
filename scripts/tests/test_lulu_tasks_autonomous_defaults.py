"""lulu-tasks orchestration stays on macros and state units."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2] / "lulu-tasks"
_SKILL = _ROOT / "SKILL.md"
_DRAFTING = _ROOT / "references" / "drafting.md"
_EVALUATING = _ROOT / "references" / "evaluating.md"
_DELIVERY = _ROOT / "references" / "delivery.md"


def test_lulu_tasks_no_execution_mode_section():
    content = _SKILL.read_text(encoding="utf-8")
    assert "## Execution Mode: Apply" not in content
    assert "### Autonomous Overrides" not in content


def test_lulu_tasks_no_execution_mode_branching():
    content = _SKILL.read_text(encoding="utf-8")
    assert "$EXECUTION_MODE" not in content
    assert "execution_mode:" not in content
    assert "guided mode" not in content.lower()


def test_lulu_tasks_feature_auto_tech_ref():
    content = _SKILL.read_text(encoding="utf-8")
    assert "Feature:" in content
    assert "--tech-ref" in content
    assert "delivered plan" in content


def test_lulu_tasks_topic_manual_confirm_paths():
    drafting = _DRAFTING.read_text(encoding="utf-8")
    delivery = _DELIVERY.read_text(encoding="utf-8")
    assert "Topic waits until the user confirms the split" in drafting
    assert "Topic waits for an explicit delivery confirmation" in delivery


def test_lulu_tasks_feature_autonomous_defaults():
    drafting = _DRAFTING.read_text(encoding="utf-8")
    evaluating = _EVALUATING.read_text(encoding="utf-8")
    delivery = _DELIVERY.read_text(encoding="utf-8")
    assert "Feature runs `$TT_ENTER_EVAL` immediately" in drafting
    assert "disposition: drafting" in evaluating
    assert "Start `lulu-code`" in delivery
    assert "auto-chain" not in _SKILL.read_text(encoding="utf-8")


def test_lulu_tasks_probe_does_not_edit_the_work_order():
    content = _EVALUATING.read_text(encoding="utf-8")
    assert "does not edit it" in content
    assert "$TT_EVAL" in content


def test_lulu_tasks_reads_skill_templates_not_fetch_cli():
    content = _DRAFTING.read_text(encoding="utf-8")
    assert "$FETCH_TEMPLATE" not in content
    assert "templates/31-work-order-tasklist-template.md" in content
    assert "templates/30-work-order-task-template.md" in content


def test_eval_methods_replace_private_runner():
    assert not (_ROOT / "eval-runner" / "SKILL.md").exists()
    assert (_ROOT / "eval" / "eval-profile.json").is_file()
    for name in (
        "compliance-crosscheck",
        "execution-admission",
    ):
        assert (_ROOT / "eval" / "methods" / f"{name}.md").is_file()
        assert (_ROOT / "eval" / "dimension-defs" / f"{name}.json").is_file()


def test_entry_skill_does_not_write_session_files():
    content = _SKILL.read_text(encoding="utf-8")
    assert "Split a delivered plan into an independently executable task-dependency list." in content
    router = content.split("## Router", 1)[1]
    assert "python3" not in router
    assert "workflow-state.md" not in content
    assert "$TT_CTX" in content
