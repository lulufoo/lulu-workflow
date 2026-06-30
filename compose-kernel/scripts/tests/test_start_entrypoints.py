#!/usr/bin/env python3
"""Tests for compose start entrypoint migration."""

from __future__ import annotations

from pathlib import Path

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]


def test_stage_skills_call_kernel_start_directly() -> None:
    for stage in ("tech-design", "tech-plan", "product-spec"):
        text = (_WORKFLOW_ROOT / stage / "SKILL.md").read_text(encoding="utf-8")
        assert 'python3 "$SKILL_ROOT/compose-kernel/scripts/core/start.py"' in text
        assert f"$SKILL_DIR/scripts/{stage}_start.py" not in text


def test_stage_start_wrappers_removed() -> None:
    for stage in ("tech-design", "tech-plan", "product-spec"):
        assert not (_WORKFLOW_ROOT / stage / "scripts" / f"{stage}_start.py").exists()
