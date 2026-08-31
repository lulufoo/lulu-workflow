#!/usr/bin/env python3
"""Tests for workflow_profile_paths.py."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_kernel"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "schema" / "session"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_kernel"))

from l_ledger_schema import build_ledger, save_l_ledger
from workflow_paths import seed_profile_pointer_for_tests
from workflow_profile_paths import (
    approval_path,
    doc_dir,
    document_path,
    eval_round_dir,
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
        save_l_ledger(rev, build_ledger(["L1"]))
        (rev / "L1").mkdir(exist_ok=True)
    return root


def test_tech_design_paths(project_root: Path):
    cycle = "feat-profile-paths"
    assert session_state_path(cycle, "lulu-design", project_root).as_posix().endswith(
        "lulu-design/session-state.md",
    )
    assert doc_dir(cycle, 1, "lulu-design", project_root).as_posix().endswith(
        "lulu-design/revision1",
    )
    assert document_path(cycle, 1, "lulu-design", project_root).name == "design-doc.md"
    assert approval_path(cycle, 1, "lulu-design", project_root).name == "human-delivery-gate.md"
    assert inductive_out_dir(cycle, "lulu-design", project_root).as_posix().endswith(
        "lulu-design/revision1/L1",
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
