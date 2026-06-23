#!/usr/bin/env python3
"""Tests for workflow_paths.load_profile session vs authoring resolution."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from workflow_paths import (  # noqa: E402
    compose_profile_path,
    load_profile,
    seed_profile_pointer_for_tests,
)


def test_load_profile_authoring_when_project_root_omitted() -> None:
    data = load_profile("tech-plan")
    assert data["profile_id"] == "tech-plan"
    assert compose_profile_path("tech-plan").is_file()


def test_load_profile_authoring_when_cycle_unresolvable(tmp_path: Path) -> None:
    data = load_profile("tech-plan", project_root=tmp_path)
    assert data["profile_id"] == "tech-plan"


def test_load_profile_session_via_pointer(tmp_path: Path) -> None:
    seed_profile_pointer_for_tests(tmp_path, "feat-load-profile", "tech-plan")
    data = load_profile("tech-plan", project_root=tmp_path, cycle_id="feat-load-profile")
    assert data["profile_id"] == "tech-plan"
    assert data["document"]["filename"] == "tech-doc.md"


def test_load_profile_raises_without_pointer_when_cycle_id_given(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="compose profile pointer|cycle cache not found"):
        load_profile("tech-plan", project_root=tmp_path, cycle_id="missing-pointer-cycle")
