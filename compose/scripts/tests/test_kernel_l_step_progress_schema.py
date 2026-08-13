#!/usr/bin/env python3
"""Tests for generic l-step-progress schema."""

from __future__ import annotations

from pathlib import Path

import pytest

import bootstrap  # noqa: F401
import l_step_progress_schema as schema  # noqa: E402


def test_tech_design_allows_inductive_initialized_and_freeedit() -> None:
    for step in ("Inductive", "Written", "FreeEdit"):
        assert schema.validate_l_step_progress(
            {"version": "1", "cycle_id": "C1", "current_step": step},
            profile_id="lulu-design",
        ) == []


def test_tech_plan_rejects_inductive() -> None:
    errors = schema.validate_l_step_progress(
        {"version": "1", "cycle_id": "C1", "current_step": "Inductive"},
        profile_id="lulu-plan",
    )

    assert any("invalid current_step" in err for err in errors)


def test_tech_plan_session_instance_allows_inductive(tmp_path: Path) -> None:
    import json

    from workflow_common import CACHE_DIR
    from workflow_paths import (
        compose_profile_path,
        load_profile_json,
        write_profile_pointer,
    )

    data = load_profile_json(compose_profile_path("lulu-plan"))
    data["pipeline"]["inductive"] = True
    instance = tmp_path / CACHE_DIR / "C1" / "lulu-plan" / "compose-profile.json"
    instance.parent.mkdir(parents=True)
    instance.write_text(json.dumps(data), encoding="utf-8")
    write_profile_pointer(tmp_path, "C1", "lulu-plan", instance)

    assert schema.validate_l_step_progress(
        {"version": "1", "cycle_id": "C1", "current_step": "Inductive"},
        profile_id="lulu-plan",
        project_root=tmp_path,
        cycle_id="C1",
    ) == []


def test_tech_plan_allows_deductive() -> None:
    assert schema.validate_l_step_progress(
        {"version": "1", "cycle_id": "C1", "current_step": "Deductive"},
        profile_id="lulu-plan",
    ) == []


def test_tech_design_rejects_deductive() -> None:
    errors = schema.validate_l_step_progress(
        {"version": "1", "cycle_id": "C1", "current_step": "Deductive"},
        profile_id="lulu-design",
    )
    assert any("invalid current_step" in err for err in errors)


def test_product_spec_allows_freeedit() -> None:
    assert schema.validate_l_step_progress(
        {"version": "1", "cycle_id": "C1", "current_step": "FreeEdit"},
        profile_id="lulu-spec",
    ) == []


def test_save_and_load_l_step_progress(tmp_path: Path) -> None:
    path = tmp_path / "l-step-progress.md"

    schema.save_l_step_progress(
        path,
        {"version": "1", "cycle_id": "C1", "current_step": "Written"},
        profile_id="lulu-plan",
    )

    assert schema.load_l_step_progress(path, profile_id="lulu-plan") == {
        "version": "1",
        "cycle_id": "C1",
        "current_step": "Written",
    }


def test_legacy_drafting_progress_hard_cut(tmp_path: Path) -> None:
    legacy = tmp_path / "drafting-progress.md"
    legacy.write_text(
        "---\nversion: 1\ncycle_id: C1\ncurrent_step: Written\n---\n",
        encoding="utf-8",
    )
    path = tmp_path / "l-step-progress.md"
    with pytest.raises(ValueError, match="drafting-progress.md is not supported"):
        schema.load_l_step_progress(path, profile_id="lulu-plan")
    with pytest.raises(ValueError, match="hard cut"):
        schema.save_l_step_progress(
            path,
            {"version": "1", "cycle_id": "C1", "current_step": "Written"},
            profile_id="lulu-plan",
        )
    with pytest.raises(ValueError, match="start a new revision"):
        schema.read_current_step(path)


def test_load_normalizes_legacy_ready_to_initialized(tmp_path: Path) -> None:
    path = tmp_path / "l-step-progress.md"
    path.write_text(
        "---\nversion: 1\ncycle_id: C1\ncurrent_step: Ready\n---\n",
        encoding="utf-8",
    )

    assert schema.validate_l_step_progress(
        {"version": "1", "cycle_id": "C1", "current_step": "Ready"},
        profile_id="lulu-plan",
    ) == []
    assert schema.load_l_step_progress(path, profile_id="lulu-plan")["current_step"] == "Written"
    assert schema.read_current_step(path) == "Written"
