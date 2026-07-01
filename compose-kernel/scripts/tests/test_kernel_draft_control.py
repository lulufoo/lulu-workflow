#!/usr/bin/env python3
"""Tests for generic compose drafting control."""

from __future__ import annotations

from pathlib import Path

import pytest

import bootstrap  # noqa: F401
import draft_control  # noqa: E402
import drafting_progress_schema as progress_schema  # noqa: E402
from workflow_profile_paths import doc_dir  # noqa: E402

from init_drafting_helpers import seed_tech_plan_session  # noqa: E402

_CYCLE = "feature-draft-generic"


def _progress_path(project_root: Path, profile_id: str) -> Path:
    return project_root / doc_dir(_CYCLE, 1, profile_id, project_root) / "drafting-progress.md"


def test_begin_inductive_rejects_non_inductive_profile(tmp_path: Path) -> None:
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, profile_id="tech-plan")

    result = draft_control.begin_inductive(_CYCLE, tmp_path, profile_id="tech-plan")

    assert result["ok"] is False
    assert "drafting.inductive is false" in result["reason"]


def test_advance_to_freeedit_rejects_profile_without_freeedit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # All shipped profiles now enable freeedit; force a disabled profile to
    # keep the rejection branch covered.
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, profile_id="product-spec")
    progress_schema.save_drafting_progress(
        _progress_path(tmp_path, "product-spec"),
        {"version": "1", "cycle_id": _CYCLE, "current_step": "Initialized"},
        profile_id="product-spec",
    )
    monkeypatch.setattr(
        draft_control,
        "load_profile",
        lambda *args, **kwargs: {"drafting": {"freeedit": False}},
    )

    result = draft_control.advance_to_freeedit(_CYCLE, tmp_path, profile_id="product-spec")

    assert result["ok"] is False
    assert "drafting.freeedit is false" in result["reason"]


def test_advance_to_freeedit_accepts_legacy_ready(tmp_path: Path) -> None:
    seed_tech_plan_session(tmp_path, cycle_id=_CYCLE, profile_id="tech-plan")
    _progress_path(tmp_path, "tech-plan").write_text(
        "---\nversion: 1\ncycle_id: feature-draft-generic\ncurrent_step: Ready\n---\n",
        encoding="utf-8",
    )

    result = draft_control.advance_to_freeedit(_CYCLE, tmp_path, profile_id="tech-plan")

    assert result["ok"] is True
    assert result["current_step"] == "FreeEdit"
