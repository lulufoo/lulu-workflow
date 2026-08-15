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

_PROFILE = _REPO / "lulu-dev-workflow" / "lulu-spec" / "compose-profile.json"

def test_spec_k0b_section_registry_has_presence() -> None:
    data = product_spec_section_registry()
    assert validate_section_registry(data) == []
    normalized = normalize_section_registry(data)
    for key in normalized["section_order"]:
        assert normalized["sections"][key]["presence"] == "required"


def test_spec_k0b_profile_points_to_direct_templates() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    compose = profile["framework_templates"]
    for key, filename in (
        ("section-registry", "section-registry.json"),
        ("section-form-registry", "section-form-registry.json"),
        ("section-kw-criteria", "section-kw-criteria.md"),
        ("role-instance", "role-instance.json"),
        ("domain-instance", "domain-instance.json"),
        ("inductive-scan-criteria", "inductive-scan-criteria.json"),
    ):
        expected = f"lulu-dev-workflow/lulu-spec/templates/{filename}"
        assert compose[key] == expected
        assert (_REPO / expected).is_file(), key
def test_spec_k0b_profile_has_no_display_layer_flag() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    assert profile["pipeline"]["inductive"] is True
    assert "display_layer" not in profile.get("pipeline", {})
    assert "outline-registry" not in (profile.get("framework_templates") or {})
