#!/usr/bin/env python3
"""Tests for stage SKILL draft-control macro migration.

Since the compose SKILL closed-loop refactor, `$DRAFT_CONTROL` is defined
once (generically, via `<profile_id>`) in the compose-kernel engine SKILL;
holders no longer redefine it locally (see
docs/biz/compose-skill-closed-loop-finishing.md §10 item 5).
"""

from __future__ import annotations

from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_ENGINE_SKILL = _WORKFLOW_ROOT / "compose-kernel" / "SKILL.md"


def test_engine_defines_generic_kernel_draft_control() -> None:
    engine_text = _ENGINE_SKILL.read_text(encoding="utf-8")
    assert (
        'python3 "$SKILL_ROOT/compose-kernel/scripts/section/draft_control.py" '
        '--cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile <profile_id> <subcommand>'
    ) in engine_text


def test_stage_skills_do_not_locally_redefine_draft_control() -> None:
    for stage in ("tech-design", "tech-plan", "product-spec"):
        text = (_WORKFLOW_ROOT / stage / "SKILL.md").read_text(encoding="utf-8")
        assert "$DRAFT_CONTROL" not in text
        assert f"$SKILL_DIR/scripts/drafting/{stage.replace('-', '_')}_draft_control.py" not in text
        assert "compose-kernel/scripts/section/draft_control.py" not in text


def test_stage_skills_no_ready_drafting_state_wording() -> None:
    for stage in ("tech-plan", "product-spec"):
        text = (_WORKFLOW_ROOT / stage / "SKILL.md").read_text(encoding="utf-8")
        assert "Drafting states**: `Ready" not in text
        assert "Drafting state (MVP):** `Ready`" not in text
