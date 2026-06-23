#!/usr/bin/env python3
"""Tests for profile_schema.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bootstrap  # noqa: F401

_SCHEMA_SESSION = Path(__file__).resolve().parents[1] / "schema" / "session"
if str(_SCHEMA_SESSION) not in sys.path:
    sys.path.insert(0, str(_SCHEMA_SESSION))

from profile_schema import _validate_profile, validate_all  # noqa: E402

_MINIMAL_ACTIVE_PROFILE = {
    "profile_id": "tech-foo",
    "stage_name": "tech-foo",
    "shell_dir": "tech-foo",
    "shell_paths": {
        "hook_guard": "tech-foo/scripts/hook_guard.py",
        "dimension_defs_dir": "tech-foo/dimension-defs",
    },
    "cache_subdir": "tech/foo",
    "framework_section": "tech-foo",
    "framework_templates": {
        "section-registry": "tpt_section_registry_url",
        "section-kw-criteria": "tpt_section_kw_criteria_url",
        "outline-registry": "tpt_outline_registry_url",
        "role-instance": "tpt_feature_role_instance_url",
        "domain-instance": "tpt_feature_domain_instance_url",
    },
    "cycle_types": ["feature"],
}


def test_validate_all_passes_current_profiles() -> None:
    assert validate_all() == []


def test_placeholder_skips_full_contract(tmp_path: Path) -> None:
    stage_dir = tmp_path / "tech-arch"
    stage_dir.mkdir()
    path = stage_dir / "compose-profile.json"
    path.write_text(
        json.dumps(
            {
                "profile_id": "tech-arch",
                "stage_name": "tech-arch",
                "status": "placeholder_phase2",
            },
        ),
        encoding="utf-8",
    )
    assert _validate_profile(path) == []


def test_active_profile_missing_shell_paths_fails(tmp_path: Path) -> None:
    stage_dir = tmp_path / "tech-foo"
    stage_dir.mkdir()
    path = stage_dir / "compose-profile.json"
    data = dict(_MINIMAL_ACTIVE_PROFILE)
    del data["shell_paths"]
    path.write_text(json.dumps(data), encoding="utf-8")
    errors = _validate_profile(path)
    assert any("missing required field 'shell_paths'" in err for err in errors)


def test_unknown_active_profile_validates_without_whitelist(tmp_path: Path) -> None:
    stage_dir = tmp_path / "tech-foo"
    stage_dir.mkdir()
    path = stage_dir / "compose-profile.json"
    path.write_text(json.dumps(_MINIMAL_ACTIVE_PROFILE), encoding="utf-8")
    assert _validate_profile(path) == []
