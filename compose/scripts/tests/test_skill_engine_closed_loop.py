#!/usr/bin/env python3
"""Hard-gate tests for the compose SKILL orchestration layer closed loop.

Acceptance criteria for holder thin-shell + engine closed loop:
this file is the executable SSOT (see also docs/domain/ssot/compose/business-ssot/compose-business-ssot.md §7).
"""

from __future__ import annotations

from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_ENGINE_SKILL = _WORKFLOW_ROOT / "compose" / "SKILL.md"
_EVAL_SKILL = _WORKFLOW_ROOT / "eval" / "SKILL.md"
_STAGES = ("lulu-design", "lulu-plan", "lulu-spec")
_HOLDER_LINE_THRESHOLD = 60


def test_engine_skill_contains_full_orchestration() -> None:
    """Item 2: engine SKILL owns Drafting / Evaluating / Delivery + Inductive gating."""
    text = _ENGINE_SKILL.read_text(encoding="utf-8")

    for heading in ("## Drafting Rules", "## Evaluating Rules", "## Delivery Rules"):
        assert heading in text, f"engine SKILL missing {heading!r}"

    assert "drafting.inductive" in text
    assert "inductive" in text.lower()
    assert "deductive" in text.lower()
    assert "begin-deductive" in text
    assert "deductive-runner" in text


def test_engine_evaluating_delegates_without_dimension_table() -> None:
    """Item 3: engine hands off to eval-rules.md, never enumerates dimensions."""
    text = _ENGINE_SKILL.read_text(encoding="utf-8")

    assert "eval/eval-rules.md" in text

    lowered = text.lower()
    for forbidden in ("| d1 ", "| d2 ", "| d3 ", "pdqa"):
        assert forbidden not in lowered, f"engine SKILL should not enumerate dimension {forbidden!r}"


def test_holder_skills_are_thin_shells() -> None:
    """Item 1: holder SKILLs stay under the line threshold and load the engine."""
    for stage in _STAGES:
        holder_path = _WORKFLOW_ROOT / stage / "SKILL.md"
        text = holder_path.read_text(encoding="utf-8")
        lines = text.count("\n") + 1
        assert lines <= _HOLDER_LINE_THRESHOLD, (
            f"{stage}/SKILL.md has {lines} lines (> {_HOLDER_LINE_THRESHOLD}); "
            "holder should delegate orchestration to compose/SKILL.md"
        )
        assert "compose/SKILL.md" in text, f"{stage}/SKILL.md must read the compose engine"

        for heading in ("## Drafting Rules", "## Evaluating Rules", "## ReadyForDelivery Rules", "## Delivery Rules"):
            assert heading not in text, f"{stage}/SKILL.md should not repeat engine heading {heading!r}"


def test_eval_skill_drops_stage_entry_table() -> None:
    """Item 4: eval SKILL no longer hardcodes stage names for adapter discovery."""
    eval_text = _EVAL_SKILL.read_text(encoding="utf-8")

    for stage in _STAGES:
        entry_script = f"{stage}/scripts/{stage}_eval_control.py"
        assert entry_script not in eval_text, f"eval/SKILL.md still hardcodes {entry_script!r}"
        stage_entry_file = _WORKFLOW_ROOT / stage / "scripts" / f"{stage}_eval_control.py"
        assert not stage_entry_file.exists(), f"{stage_entry_file} should have been deleted (eval V2)"


def test_eval_control_macro_is_generic_and_holder_free() -> None:
    """Item 5: $EVAL_CONTROL is defined once, generically, in the engine; holders don't."""
    engine_text = _ENGINE_SKILL.read_text(encoding="utf-8")
    assert '`$EVAL_CONTROL`' in engine_text
    assert "eval/scripts/eval_entry.py" in engine_text

    for stage in _STAGES:
        holder_text = (_WORKFLOW_ROOT / stage / "SKILL.md").read_text(encoding="utf-8")
        assert "$EVAL_CONTROL" not in holder_text, f"{stage}/SKILL.md should not redefine $EVAL_CONTROL"
