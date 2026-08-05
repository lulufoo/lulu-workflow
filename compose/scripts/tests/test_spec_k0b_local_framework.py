#!/usr/bin/env python3
"""K0b: lulu-spec section presence (skill-builtin section-registry SSOT)."""

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
sys.path.insert(0, str(Path(__file__).resolve().parent))

from framework_template_sources import product_spec_section_registry  # noqa: E402
from section_registry_schema import (  # noqa: E402
    normalize_section_registry,
    validate_section_registry,
)

_SKILL_CONFIG = (
    _REPO / "skill-config" / "lulu-dev-workflow" / "stages" / "lulu-spec.json"
)
_PROFILE = _REPO / "lulu-dev-workflow" / "lulu-spec" / "compose-profile.json"

def test_spec_k0b_section_registry_has_presence() -> None:
    data = product_spec_section_registry()
    assert validate_section_registry(data) == []
    normalized = normalize_section_registry(data)
    for key in normalized["section_order"]:
        assert normalized["sections"][key]["presence"] == "required"


def test_spec_k0b_skill_config_points_upstream() -> None:
    cfg = json.loads(_SKILL_CONFIG.read_text(encoding="utf-8"))
    compose = cfg["compose"]
    for key in (
        "pst_section_registry_url",
        "pst_section_form_registry_url",
        "pst_section_kw_criteria_url",
        "pst_feature_role_instance_url",
        "pst_feature_domain_instance_url",
    ):
        assert compose[key].startswith("lulu-dev-workflow/lulu-spec/templates/"), key
        assert (_REPO / compose[key]).is_file(), key
    assert compose["pst_inductive_scan_criteria_url"].startswith("https://")


def test_spec_k0b_profile_has_no_display_layer_flag() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    assert profile["pipeline"]["inductive"] is True
    assert "display_layer" not in profile.get("pipeline", {})
    assert "outline-registry" not in (profile.get("framework_templates") or {})
