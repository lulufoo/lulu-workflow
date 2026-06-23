#!/usr/bin/env python3
"""Tests for workflow_profile_paths.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from workflow_paths import seed_profile_pointer_for_tests
from workflow_profile_paths import (
    approval_path,
    doc_dir,
    document_path,
    eval_round_dir,
    session_state_path,
)


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path
    seed_profile_pointer_for_tests(root, "feat-profile-paths", "tech-design")
    seed_profile_pointer_for_tests(root, "feat-profile-paths", "tech-plan")
    return root


def test_tech_design_paths(project_root: Path):
    cycle = "feat-profile-paths"
    assert session_state_path(cycle, "tech-design", project_root).as_posix().endswith(
        "tech/design/session-state.md",
    )
    assert doc_dir(cycle, 1, "tech-design", project_root).as_posix().endswith(
        "tech/design/revision1",
    )
    assert document_path(cycle, 1, "tech-design", project_root).name == "design-doc.md"
    assert approval_path(cycle, 1, "tech-design", project_root).name == "human-delivery-gate.md"


def test_tech_plan_paths_unchanged(project_root: Path):
    cycle = "feat-profile-paths"
    assert session_state_path(cycle, "tech-plan", project_root).as_posix().endswith(
        "tech/plan/session-state.md",
    )
    assert document_path(cycle, 1, "tech-plan", project_root).name == "tech-doc.md"
    assert eval_round_dir(cycle, 1, 2, "tech-plan", project_root).as_posix().endswith(
        "tech/plan/revision1/evaluate2",
    )
