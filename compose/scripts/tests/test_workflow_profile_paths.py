#!/usr/bin/env python3
"""Tests for workflow_profile_paths.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_kernel"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "schema" / "session"))

from execution_state_schema import build_execution_state, save_execution_state
from workflow_paths import seed_profile_pointer_for_tests
from workflow_profile_paths import (
    approval_path,
    doc_dir,
    document_path,
    eval_round_dir,
    execution_dir_rel,
    inductive_out_dir,
    session_state_path,
)


@pytest.fixture
def project_root(tmp_path: Path) -> Path:
    root = tmp_path
    seed_profile_pointer_for_tests(root, "feat-profile-paths", "lulu-design")
    seed_profile_pointer_for_tests(root, "feat-profile-paths", "lulu-plan")
    for profile in ("lulu-design", "lulu-plan"):
        rev = root / doc_dir("feat-profile-paths", 1, profile, root)
        rev.mkdir(parents=True, exist_ok=True)
        save_execution_state(rev, build_execution_state())
        (rev / "execution").mkdir(exist_ok=True)
    return root


def test_tech_design_paths(project_root: Path):
    cycle = "feat-profile-paths"
    assert session_state_path(cycle, "lulu-design", project_root).as_posix().endswith(
        "lulu-design/session-state.md",
    )
    assert doc_dir(cycle, 1, "lulu-design", project_root).as_posix().endswith(
        "lulu-design/revision1",
    )
    assert document_path(cycle, 1, "lulu-design", project_root).as_posix().endswith(
        "lulu-design/revision1/execution/design-doc.md",
    )
    assert approval_path(cycle, 1, "lulu-design", project_root).name == "human-delivery-gate.md"
    assert inductive_out_dir(cycle, "lulu-design", project_root).as_posix().endswith(
        "lulu-design/revision1/execution",
    )
    assert execution_dir_rel(cycle, 1, "lulu-design", project_root).as_posix().endswith(
        "lulu-design/revision1/execution",
    )


def test_tech_plan_paths_unchanged(project_root: Path):
    cycle = "feat-profile-paths"
    assert session_state_path(cycle, "lulu-plan", project_root).as_posix().endswith(
        "lulu-plan/session-state.md",
    )
    assert document_path(cycle, 1, "lulu-plan", project_root).name == "tech-doc.md"
    assert eval_round_dir(cycle, 1, 2, "lulu-plan", project_root).as_posix().endswith(
        "lulu-plan/revision1/evaluate2",
    )
