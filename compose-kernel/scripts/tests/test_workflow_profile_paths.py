#!/usr/bin/env python3
"""Tests for workflow_profile_paths.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from workflow_profile_paths import (
    approval_path,
    doc_dir,
    document_path,
    eval_round_dir,
    session_state_path,
)


def test_tech_design_paths():
    cycle = "feat-profile-paths"
    assert session_state_path(cycle, "tech-design").as_posix().endswith(
        "tech/design/session-state.md",
    )
    assert doc_dir(cycle, 1, "tech-design").as_posix().endswith(
        "tech/design/revision1",
    )
    assert document_path(cycle, 1, "tech-design").name == "design-doc.md"
    assert approval_path(cycle, 1, "tech-design").name == "human-delivery-gate.md"


def test_tech_plan_paths_unchanged():
    cycle = "feat-profile-paths"
    assert session_state_path(cycle, "tech-plan").as_posix().endswith(
        "tech/plan/session-state.md",
    )
    assert document_path(cycle, 1, "tech-plan").name == "tech-doc.md"
    assert eval_round_dir(cycle, 1, 2, "tech-plan").as_posix().endswith(
        "tech/plan/revision1/evaluate2",
    )
