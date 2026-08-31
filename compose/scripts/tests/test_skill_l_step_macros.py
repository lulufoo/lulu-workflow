#!/usr/bin/env python3
"""Tests for stage SKILL draft-control macro migration.

Since the compose SKILL closed-loop refactor, `$L_STEP` is defined
once in `compose/references/l-execution.md`; holders no longer redefine it
locally (see docs/domain/ssot/compose/business-ssot/compose-business-ssot.md §7;
this test is the executable check).
"""

from __future__ import annotations

from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_ENGINE_SKILL = _WORKFLOW_ROOT / "compose" / "SKILL.md"
_INNER = _WORKFLOW_ROOT / "compose" / "references" / "l-execution.md"


def test_engine_defines_generic_l_step() -> None:
    inner_text = _INNER.read_text(encoding="utf-8")
    engine_text = _ENGINE_SKILL.read_text(encoding="utf-8")
    assert (
        'python3 "$SKILL_ROOT/compose/scripts/session/l_step_control.py" '
        '--cycle-id "$CYCLE_ID" --project-root "$(pwd)" <subcommand>'
    ) in inner_text
    assert "$L_STEP" not in engine_text
    assert "--profile <profile_id>" not in inner_text
    assert "--profile <profile_id>" not in engine_text


def test_stage_skills_do_not_locally_redefine_l_step() -> None:
    for stage in ("lulu-design", "lulu-plan", "lulu-spec"):
        text = (_WORKFLOW_ROOT / stage / "SKILL.md").read_text(encoding="utf-8")
        assert "$L_STEP" not in text
        assert f"$SKILL_DIR/scripts/pipeline/{stage.replace('-', '_')}_l_step_control.py" not in text
        assert "compose/scripts/session/l_step_control.py" not in text


def test_stage_skills_no_ready_pipeline_state_wording() -> None:
    for stage in ("lulu-plan", "lulu-spec"):
        text = (_WORKFLOW_ROOT / stage / "SKILL.md").read_text(encoding="utf-8")
        assert "Drafting states**: `Ready" not in text
        assert "Drafting state (MVP):** `Ready`" not in text
