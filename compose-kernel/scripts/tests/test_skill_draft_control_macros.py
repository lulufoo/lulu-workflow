#!/usr/bin/env python3
"""Tests for stage SKILL draft-control macro migration."""

from __future__ import annotations

from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]


def test_stage_skills_use_kernel_draft_control() -> None:
    for stage in ("tech-design", "tech-plan", "product-spec"):
        text = (_WORKFLOW_ROOT / stage / "SKILL.md").read_text(encoding="utf-8")
        assert (
            f'python3 "$SKILL_ROOT/compose-kernel/scripts/section/draft_control.py" '
            f'--cycle-id "$CYCLE_ID" --project-root "$(pwd)" --profile {stage} <subcommand>'
        ) in text
        assert f"$SKILL_DIR/scripts/drafting/{stage.replace('-', '_')}_draft_control.py" not in text


def test_stage_skills_no_ready_drafting_state_wording() -> None:
    for stage in ("tech-plan", "product-spec"):
        text = (_WORKFLOW_ROOT / stage / "SKILL.md").read_text(encoding="utf-8")
        assert "Drafting states**: `Ready" not in text
        assert "Drafting state (MVP):** `Ready`" not in text
