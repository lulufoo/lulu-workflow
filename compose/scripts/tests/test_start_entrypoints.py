#!/usr/bin/env python3
"""Tests for compose start entrypoint migration.

Since the compose SKILL closed-loop refactor, the `start.py` invocation is
defined once (generically) in the compose engine SKILL's `$START_COMPOSE`
macro / § start; holders reference `$START_COMPOSE` with their concrete
`--profile <stage>` flag rather than repeating the raw script invocation
(see docs/domain/ssot/compose/business-ssot/compose-business-ssot.md §7; this test is the executable check).
"""

from __future__ import annotations

from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_ENGINE_SKILL = _WORKFLOW_ROOT / "compose" / "SKILL.md"


def test_engine_calls_kernel_start_directly() -> None:
    engine_text = _ENGINE_SKILL.read_text(encoding="utf-8")
    assert 'python3 "$SKILL_ROOT/compose/scripts/core/start.py"' in engine_text


def test_stage_skills_reference_start_macro_with_own_profile() -> None:
    for stage in ("lulu-design", "lulu-plan", "lulu-spec"):
        text = (_WORKFLOW_ROOT / stage / "SKILL.md").read_text(encoding="utf-8")
        assert "$START_COMPOSE" in text
        assert f"--profile {stage} " in text
        assert f"$SKILL_DIR/scripts/{stage}_start.py" not in text
        assert 'python3 "$SKILL_ROOT/compose/scripts/core/start.py"' not in text


def test_stage_start_wrappers_removed() -> None:
    for stage in ("lulu-design", "lulu-plan", "lulu-spec"):
        assert not (_WORKFLOW_ROOT / stage / "scripts" / f"{stage}_start.py").exists()


def test_start_macro_requires_holder_profile_path() -> None:
    engine_text = _ENGINE_SKILL.read_text(encoding="utf-8")
    assert '--profile-path "$SKILL_DIR/compose-profile.json"' not in engine_text
    assert "--profile-path" in engine_text


def test_plan_skill_materializes_runtime_profile() -> None:
    text = (_WORKFLOW_ROOT / "lulu-plan" / "SKILL.md").read_text(encoding="utf-8")
    assert "$PLAN_PROFILE" in text
    assert "tech_plan_profile_control.py" in text
