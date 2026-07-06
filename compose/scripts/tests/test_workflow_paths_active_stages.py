#!/usr/bin/env python3
"""Tests for active_compose_stage_ids discovery."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_CORE = Path(__file__).resolve().parents[1] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))

from workflow_paths import active_compose_stage_ids  # noqa: E402

_MINIMAL_PROFILE = {
    "profile_id": "lulu-foo",
    "stage_name": "lulu-foo",
}


def _write_profile(stage_dir: Path, data: dict) -> None:
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "compose-profile.json").write_text(
        json.dumps(data),
        encoding="utf-8",
    )


def test_active_compose_stage_ids_skips_placeholder(tmp_path: Path) -> None:
    _write_profile(
        tmp_path / "lulu-arch",
        {
            "profile_id": "lulu-arch",
            "stage_name": "lulu-arch",
            "status": "placeholder_phase2",
        },
    )
    _write_profile(tmp_path / "lulu-plan", dict(_MINIMAL_PROFILE, profile_id="lulu-plan"))

    assert active_compose_stage_ids(workflow_root=tmp_path) == ("lulu-plan",)


def test_active_compose_stage_ids_skips_profile_id_mismatch(tmp_path: Path) -> None:
    _write_profile(
        tmp_path / "lulu-plan",
        {
            "profile_id": "lulu-design",
            "stage_name": "lulu-design",
        },
    )

    assert active_compose_stage_ids(workflow_root=tmp_path) == ()


def test_active_compose_stage_ids_discovers_sorted_active_profiles(tmp_path: Path) -> None:
    _write_profile(tmp_path / "lulu-spec", dict(_MINIMAL_PROFILE, profile_id="lulu-spec"))
    _write_profile(tmp_path / "lulu-plan", dict(_MINIMAL_PROFILE, profile_id="lulu-plan"))
    _write_profile(tmp_path / "lulu-design", dict(_MINIMAL_PROFILE, profile_id="lulu-design"))

    assert active_compose_stage_ids(workflow_root=tmp_path) == (
        "lulu-design",
        "lulu-plan",
        "lulu-spec",
    )
