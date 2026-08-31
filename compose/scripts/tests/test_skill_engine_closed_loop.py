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
    """Item 2: engine SKILL owns outer Working loop + Delivery."""
    text = _ENGINE_SKILL.read_text(encoding="utf-8")
    inner = (_WORKFLOW_ROOT / "compose" / "references" / "l-execution.md").read_text(
        encoding="utf-8"
    )

    for heading in (
        "## Inputs",
        "## Script Macros",
        "## Lifecycle",
        "## Entry",
        "### Start",
        "### Bind context",
        "## Split",
        "## Working",
        "### Principles",
        "### Current focus",
        "### Move forward",
        "### Revise prefix",
        "### Observe",
        "### Exit",
        "## ReadyForDelivery",
        "## Delivery",
    ):
        assert heading in text, f"engine SKILL missing {heading!r}"

    assert "stateDiagram-v2" in text
    working = text.split("## Working", 1)[1].split("## ReadyForDelivery", 1)[0]
    assert "#### " not in working

    for heading in (
        "## Script Macros",
        "## Fact Intake",
        "## Inductive",
        "## Deductive",
        "## Writing",
        "## FreeEdit",
        "## Evaluating",
    ):
        assert heading in inner, f"l-execution.md missing {heading!r}"

    assert "$L_STEP" in inner
    assert "$ROLE_PROMPT" in inner

    assert "## Session bootstrap" not in text
    assert "## Drafting Rules" not in text
    assert "### Drafting" not in text
    assert "## Evaluating Rules" not in text
    assert "begin-deductive" not in text
    assert "begin-inductive" not in text
    assert "assemble-package" not in text
    assert "$SCOPE_PACKAGE" in text
    assert "$L_STEP" not in text
    assert "$RESOLVE_ROLE" not in text
    assert "$RESOLVE_DOMAIN" not in text
    assert "$L_SHELL" in text
    assert "$DRAFT_CONTROL" not in text
    assert "leave-split" in text
    assert "lock-hard-mirror" not in text
    assert "check-split-ready" not in text
    assert "split-runner" not in text
    assert "assemble-index --confirm" not in text
    assert not (_WORKFLOW_ROOT / "compose" / "split-runner").exists()


def test_engine_evaluating_delegates_without_dimension_table() -> None:
    """Item 3: inner L-execution hands off to Eval without dimensions."""
    text = (
        _WORKFLOW_ROOT / "compose" / "references" / "l-execution.md"
    ).read_text(encoding="utf-8")

    assert "eval/SKILL.md" in text
    assert "eval/eval-rules.md" not in text

    lowered = text.lower()
    for forbidden in ("| d1 ", "| d2 ", "| d3 ", "pdqa"):
        assert forbidden not in lowered, f"l-execution.md should not enumerate dimension {forbidden!r}"


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

        for heading in (
            "## Working Rules",
            "## Drafting Rules",
            "## Evaluating Rules",
            "### Drafting",
            "## ReadyForDelivery Rules",
            "## Delivery Rules",
        ):
            assert heading not in text, f"{stage}/SKILL.md should not repeat engine heading {heading!r}"


def test_eval_skill_drops_stage_entry_table() -> None:
    """Item 4: eval SKILL no longer hardcodes stage names for adapter discovery."""
    eval_text = _EVAL_SKILL.read_text(encoding="utf-8")

    for stage in _STAGES:
        entry_script = f"{stage}/scripts/{stage}_eval_control.py"
        assert entry_script not in eval_text, f"eval/SKILL.md still hardcodes {entry_script!r}"
        stage_entry_file = _WORKFLOW_ROOT / stage / "scripts" / f"{stage}_eval_control.py"
        assert not stage_entry_file.exists(), f"{stage_entry_file} should have been deleted (eval V2)"


def test_eval_control_macro_is_eval_owned_and_holder_free() -> None:
    """Item 5: eval SKILL defines $EVAL_CONTROL; callers bind adapter-config only."""
    eval_text = _EVAL_SKILL.read_text(encoding="utf-8")
    assert "| `$EVAL_CONTROL` |" in eval_text
    assert "eval/scripts/eval_entry.py" in eval_text
    assert "$EVAL_ADAPTER_CONFIG" in eval_text

    inner_text = (
        _WORKFLOW_ROOT / "compose" / "references" / "l-execution.md"
    ).read_text(encoding="utf-8")
    assert "| `$EVAL_CONTROL` |" not in inner_text
    assert "| `$COMPOSE_EVAL_ADAPTER` |" in inner_text
    assert "compose/scripts/eval/compose_eval_control.py" in inner_text
    assert "$EVAL_CONTROL begin-eval-round" in inner_text

    for stage in _STAGES:
        holder_text = (_WORKFLOW_ROOT / stage / "SKILL.md").read_text(encoding="utf-8")
        assert "$EVAL_CONTROL" not in holder_text, f"{stage}/SKILL.md should not redefine $EVAL_CONTROL"
