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


def test_lulu_tasks_reference_comes_from_delivered_refs():
    content = _SKILL.read_text(encoding="utf-8")
    assert "--tech-ref" not in content
    assert "delivered plan" in content
    assert "approach decision" in content


def test_lulu_tasks_has_no_topic_branches():
    for unit in (_SKILL, _DRAFTING, _DELIVERY):
        assert "Topic" not in unit.read_text(encoding="utf-8")


def test_lulu_tasks_feature_autonomous_defaults():
    drafting = _DRAFTING.read_text(encoding="utf-8")
    evaluating = _EVALUATING.read_text(encoding="utf-8")
    delivery = _DELIVERY.read_text(encoding="utf-8")
    assert "Run `$TT_ENTER_EVAL`" in drafting
    assert "disposition: drafting" in evaluating
    assert "Start `lulu-exec`" in delivery
    assert "auto-chain" not in _SKILL.read_text(encoding="utf-8")


def test_lulu_tasks_remediation_edits_task_chapters_only():
    content = _EVALUATING.read_text(encoding="utf-8")
    assert "Eval remediates task chapters in place" in content
    assert "tasks-scope-rejected" in content
    assert "route-remediation-result" in content
    assert "$TT_EVAL" in content


def test_lulu_tasks_reads_skill_templates_not_fetch_cli():
    content = _DRAFTING.read_text(encoding="utf-8")
    assert "$FETCH_TEMPLATE" not in content
    assert "templates/31-work-order-tasklist-template.md" in content
    assert "templates/30-work-order-task-template.md" in content


def test_eval_methods_replace_private_runner():
    import json

    assert not (_ROOT / "eval-runner" / "SKILL.md").exists()
    profile = json.loads((_ROOT / "eval" / "eval-profile.json").read_text(encoding="utf-8"))
    assert profile["eval_capability"] == "full-remediation"
    for name in (
        "compliance-crosscheck",
        "execution-admission",
    ):
        assert (_ROOT / "eval" / "methods" / f"{name}.md").is_file()
        assert (_ROOT / "eval" / "dimension-defs" / f"{name}.json").is_file()


def test_entry_skill_does_not_write_session_files():
    content = _SKILL.read_text(encoding="utf-8")
    assert "into an independently executable task-dependency list." in content
    router = content.split("## Router", 1)[1]
    assert "python3" not in router
    assert "workflow-state.md" not in content
    assert "$TT_CTX" in content
