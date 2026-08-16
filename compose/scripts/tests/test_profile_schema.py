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
        "role-instance": "tpt_feature_role_instance_url",
        "domain-instance": "tpt_feature_domain_instance_url",
    },
    "pipeline": {
        "inductive": False,
        "freeedit": True,
        "code_grounding": False,
        "post_writing_options": ["freeedit", "evaluate"],
    },
    "eval": {
        "workflow_id": "tech-foo",
        "contributor_module": "tech-foo/scripts/eval/tech_foo_eval_contributor.py",
        "contributor_class": "TechFooEvalContributor",
        "eval_capability": "full-remediation",
    },
    "cycle_types": ["feature"],
}


def test_validate_all_passes_current_profiles() -> None:
    assert validate_all() == []


def test_placeholder_skips_full_contract(tmp_path: Path) -> None:
    stage_dir = tmp_path / "lulu-arch"
    stage_dir.mkdir()
    path = stage_dir / "compose-profile.json"
    path.write_text(
        json.dumps(
            {
                "profile_id": "lulu-arch",
                "stage_name": "lulu-arch",
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


def test_active_profile_missing_pipeline_fails(tmp_path: Path) -> None:
    stage_dir = tmp_path / "tech-foo"
    stage_dir.mkdir()
    path = stage_dir / "compose-profile.json"
    data = dict(_MINIMAL_ACTIVE_PROFILE)
    del data["pipeline"]
    path.write_text(json.dumps(data), encoding="utf-8")
    errors = _validate_profile(path)
    assert any("missing required field 'pipeline'" in err for err in errors)


def test_active_profile_rejects_unknown_post_writing_option(tmp_path: Path) -> None:
    stage_dir = tmp_path / "tech-foo"
    stage_dir.mkdir()
    path = stage_dir / "compose-profile.json"
    data = dict(_MINIMAL_ACTIVE_PROFILE)
    data["pipeline"] = {
        "inductive": False,
        "freeedit": True,
        "code_grounding": False,
        "post_writing_options": ["freeedit", "round"],
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    errors = _validate_profile(path)
    assert any("unknown pipeline.post_writing_options value 'round'" in err for err in errors)


def test_active_profile_rejects_retired_start_block(tmp_path: Path) -> None:
    stage_dir = tmp_path / "tech-foo"
    stage_dir.mkdir()
    path = stage_dir / "compose-profile.json"
    data = dict(_MINIMAL_ACTIVE_PROFILE)
    data["start"] = {"adapter_module": "tech-foo/scripts/start/tech_foo_start_adapter.py"}
    path.write_text(json.dumps(data), encoding="utf-8")
    errors = _validate_profile(path)
    assert any("start adapter contract retired" in err for err in errors)


def test_active_profile_missing_eval_contributor_class_fails(tmp_path: Path) -> None:
    stage_dir = tmp_path / "tech-foo"
    stage_dir.mkdir()
    path = stage_dir / "compose-profile.json"
    data = dict(_MINIMAL_ACTIVE_PROFILE)
    data["eval"] = {
        "workflow_id": "tech-foo",
        "contributor_module": "tech-foo/scripts/eval/tech_foo_eval_contributor.py",
    }
    path.write_text(json.dumps(data), encoding="utf-8")
    errors = _validate_profile(path)
    assert any("missing eval.contributor_class" in err for err in errors)


def test_active_profile_rejects_retired_display_layer(tmp_path: Path) -> None:
    stage_dir = tmp_path / "tech-foo"
    stage_dir.mkdir()
    path = stage_dir / "compose-profile.json"
    data = dict(_MINIMAL_ACTIVE_PROFILE)
    data["pipeline"] = dict(data["pipeline"])
    data["pipeline"]["display_layer"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    errors = _validate_profile(path)
    assert any("display_layer retired" in err for err in errors)


def test_active_profile_omits_display_layer_without_error(tmp_path: Path) -> None:
    stage_dir = tmp_path / "tech-foo"
    stage_dir.mkdir()
    path = stage_dir / "compose-profile.json"
    path.write_text(json.dumps(_MINIMAL_ACTIVE_PROFILE), encoding="utf-8")
    assert "display_layer" not in _MINIMAL_ACTIVE_PROFILE["pipeline"]
    assert _validate_profile(path) == []


def test_unknown_active_profile_validates_without_whitelist(tmp_path: Path) -> None:
    stage_dir = tmp_path / "tech-foo"
    stage_dir.mkdir()
    path = stage_dir / "compose-profile.json"
    path.write_text(json.dumps(_MINIMAL_ACTIVE_PROFILE), encoding="utf-8")
    assert _validate_profile(path) == []
