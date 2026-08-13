#!/usr/bin/env python3
"""Tests for compose start entrypoint migration.

Since the compose SKILL closed-loop refactor, the `start.py` invocation is
defined once (generically) in the compose engine SKILL's `$START_COMPOSE`
macro / § start; holders bind `$PROFILE_PATH` (start reads `profile_id` from
that JSON) rather than repeating CLI flags or the raw script invocation
(see docs/domain/ssot/compose/business-ssot/compose-business-ssot.md §7; this test is the executable check).
"""

from __future__ import annotations

from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_ENGINE_SKILL = _WORKFLOW_ROOT / "compose" / "SKILL.md"


def test_engine_registers_start_only_in_macro_table() -> None:
    engine_text = _ENGINE_SKILL.read_text(encoding="utf-8")
    orchestration, macro_table = engine_text.split("## Script Macros", maxsplit=1)
    invocation = 'python3 "$SKILL_ROOT/compose/scripts/core/start.py"'
    assert invocation not in orchestration
    assert invocation in macro_table
    assert '## Inputs' in orchestration
    assert '| `$PROFILE_PATH` | yes |' in orchestration
    assert '--profile-path "$PROFILE_PATH"' in macro_table
    assert '--scope-package "$SCOPE_PACKAGE"' in macro_table
    assert "| `$SCOPE_PACKAGE` | yes |" in orchestration
    assert "$START_COMPOSE" in macro_table
    assert "New revision" not in orchestration
    assert "Same-revision resume" not in orchestration


def test_static_profile_holders_bind_compose_inputs() -> None:
    for stage in ("lulu-arch", "lulu-blueprint", "lulu-design", "lulu-spec"):
        text = (_WORKFLOW_ROOT / stage / "SKILL.md").read_text(encoding="utf-8")
        assert "$START_COMPOSE" not in text
        assert "$SCOPE_PACKAGE" in text
        assert "$PROFILE_PATH" in text
        assert f"--profile {stage} " not in text
        assert "--profile-path" not in text
        assert f"$SKILL_DIR/scripts/{stage}_start.py" not in text
        assert 'python3 "$SKILL_ROOT/compose/scripts/core/start.py"' not in text
        assert "## Start" in text


def test_stage_start_wrappers_removed() -> None:
    for stage in ("lulu-design", "lulu-plan", "lulu-spec"):
        assert not (_WORKFLOW_ROOT / stage / "scripts" / f"{stage}_start.py").exists()


def test_start_macro_consumes_compose_profile_input() -> None:
    engine_text = _ENGINE_SKILL.read_text(encoding="utf-8")
    assert '--profile-path "$SKILL_DIR/compose-profile.json"' not in engine_text
    assert '--profile-path "$PROFILE_PATH"' in engine_text


def test_plan_skill_hands_stage_inputs_to_session_bootstrap() -> None:
    text = (_WORKFLOW_ROOT / "lulu-plan" / "SKILL.md").read_text(encoding="utf-8")
    for heading in (
        "## Stage Contract",
        "## Runtime Foundation",
        "## Compose Inputs",
        "## Compose Handoff",
        "## Script Macros",
    ):
        assert heading in text
    assert "$PLAN_PREFLIGHT" in text
    assert "tech_plan_preflight.py" in text
    assert '--project-root "$PROJECT_ROOT"' in text
    assert '$(pwd)' not in text
    assert "$START_COMPOSE" not in text
    assert "## Start" in text
    assert "$PROFILE_PATH" in text
    assert "$SCOPE_PACKAGE" in text
    assert "--profile-path" not in text
    assert "Resume" not in text
    assert "--profile lulu-plan " not in text
    assert "$SKILL_DIR/scripts/lulu-plan_start.py" not in text
    assert 'python3 "$SKILL_ROOT/compose/scripts/core/start.py"' not in text
