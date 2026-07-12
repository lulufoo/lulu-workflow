#!/usr/bin/env python3
"""K0b: lulu-blueprint local candidates outline + presence + display_layer flip."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
_SECTION_SCHEMA = (
    _REPO
    / "lulu-dev-workflow"
    / "compose"
    / "scripts"
    / "schema"
    / "section"
    / "registry"
)
sys.path.insert(0, str(_SECTION_SCHEMA))

from outline_registry_schema import (  # noqa: E402
    normalize_outline_registry,
    validate_outline_candidates_alignment,
    validate_outline_registry,
)
from section_registry_schema import (  # noqa: E402
    normalize_section_registry,
    validate_section_registry,
)

_FRAMEWORK = _REPO / "lulu-dev-workflow" / "lulu-blueprint" / "framework"
_SECTION_PATH = _FRAMEWORK / "product-blueprint-topic-section-registry.json"
_OUTLINE_PATH = _FRAMEWORK / "product-blueprint-topic-outline-registry.json"
_SKILL_CONFIG = (
    _REPO / "skill-config" / "lulu-dev-workflow" / "stages" / "lulu-blueprint.json"
)
_PROFILE = _REPO / "lulu-dev-workflow" / "lulu-blueprint" / "compose-profile.json"


def test_blueprint_k0b_section_registry_presence_and_edges() -> None:
    data = json.loads(_SECTION_PATH.read_text(encoding="utf-8"))
    assert validate_section_registry(data) == []
    normalized = normalize_section_registry(data)
    for key in normalized["section_order"]:
        expected = "optional" if key == "OQ" else "required"
        assert normalized["sections"][key]["presence"] == expected
    assert normalized["sections"]["PR"]["relations"]["PS"] == "instantiate"


def test_blueprint_k0b_outline_is_candidates_shaped() -> None:
    data = json.loads(_OUTLINE_PATH.read_text(encoding="utf-8"))
    assert "candidates" in data
    assert "outline_order" not in data
    assert "blocks" not in data
    assert validate_outline_registry(data) == []
    outline = normalize_outline_registry(data)
    section = normalize_section_registry(
        json.loads(_SECTION_PATH.read_text(encoding="utf-8"))
    )
    assert validate_outline_candidates_alignment(outline, section) == []
    blocks = {c["block"]: c["anchor_lenses"] for c in outline["candidates"]}
    assert blocks == {
        "cand-SI": ["SI"],
        "cand-BD": ["BD"],
        "cand-PS": ["PS"],
        "cand-PR": ["PR"],
        "cand-OQ": ["OQ"],
    }


def test_blueprint_k0b_skill_config_points_local() -> None:
    cfg = json.loads(_SKILL_CONFIG.read_text(encoding="utf-8"))
    compose = cfg["compose"]
    assert compose["pbt_section_registry_url"].startswith("lulu-dev-workflow/")
    assert compose["pbt_outline_registry_url"].startswith("lulu-dev-workflow/")
    assert (_REPO / compose["pbt_section_registry_url"]).is_file()
    assert (_REPO / compose["pbt_outline_registry_url"]).is_file()
    for remote_key in (
        "pbt_section_form_registry_url",
        "pbt_section_kw_criteria_url",
        "pbt_topic_role_instance_url",
        "pbt_topic_domain_instance_url",
    ):
        assert compose[remote_key].startswith("https://"), remote_key
    assert cfg["eval"]["pbt_blueprint_quality_framework_url"].startswith("https://")


def test_blueprint_k0b_profile_display_layer_true() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    assert profile["drafting"]["inductive"] is False
    assert profile["drafting"]["display_layer"] is True
