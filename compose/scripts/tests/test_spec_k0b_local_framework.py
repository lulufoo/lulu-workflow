#!/usr/bin/env python3
"""K0b: lulu-spec section presence (upstream framework SSOT)."""

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
_GH_SPEC = (
    "https://github.com/lulufoo/lulu-workflow-framework/blob/main/"
    "lulu-dev-workflow/template/spec/"
)


def test_spec_k0b_section_registry_has_presence() -> None:
    data = product_spec_section_registry()
    assert validate_section_registry(data) == []
    normalized = normalize_section_registry(data)
    for key in normalized["section_order"]:
        assert normalized["sections"][key]["presence"] == "required"


def test_spec_k0b_skill_config_points_upstream() -> None:
    cfg = json.loads(_SKILL_CONFIG.read_text(encoding="utf-8"))
    compose = cfg["compose"]
    assert compose["pst_section_registry_url"] == (
        f"{_GH_SPEC}20-product-spec-section-registry.json"
    )


def test_spec_k0b_profile_has_no_display_layer_flag() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    assert profile["drafting"]["inductive"] is True
    assert "display_layer" not in profile.get("drafting", {})
    assert "outline-registry" not in (profile.get("framework_templates") or {})
