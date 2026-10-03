#!/usr/bin/env python3
"""K0b: lulu-design section presence (skill-builtin section-registry SSOT)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SECTION_SCHEMA = (
    _REPO
   
    / "compose"
    / "scripts"
    / "schema"
    / "section"
    / "registry"
)
sys.path.insert(0, str(_SECTION_SCHEMA))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from framework_template_sources import tech_design_section_registry  # noqa: E402
from section_registry_schema import (  # noqa: E402
    normalize_section_registry,
    validate_section_registry,
)

_PROFILE = _REPO /  "lulu-design" / "compose-profile.json"

def test_design_k0b_section_registry_has_supply() -> None:
    from section_registry_schema import lens_key_sequence

    data = tech_design_section_registry()
    assert validate_section_registry(data) == []
    normalized = normalize_section_registry(data)
    keys = lens_key_sequence(normalized)
    assert normalized.get("section_order") == list(data["sections"].keys())
    for key in keys:
        supply = normalized["sections"][key]["supply"]
        assert supply in {"ask", "none"}
    # Lens V2 seams / risks / deps are not asked or derived (CMP/OD removed)
    assert normalized["sections"]["SEAM"]["supply"] == "none"
    assert normalized["sections"]["RISK"]["supply"] == "none"
    assert normalized["sections"]["DEP"]["supply"] == "none"
    assert "CMP" not in keys
    assert "GOAL" in keys and "SCOPE" in keys and "DECISION" in keys


def test_design_k0b_profile_points_to_direct_templates() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    compose = profile["framework_templates"]
    assert compose["section-registry"] == (
        "lulu-workflow/lulu-design/templates/section-registry.json"
    )
    assert compose["section-form-registry"] == (
        "lulu-workflow/lulu-design/templates/section-form-registry.json"
    )
    # Prefix = skill runtime root; remainder is under installed/source skill tree.
    skill_root = _REPO
    for key, filename in (
        ("section-registry", "section-registry.json"),
        ("section-form-registry", "section-form-registry.json"),
        ("section-kw-criteria", "section-kw-criteria.md"),
        ("role-instance", "role-instance.json"),
        ("domain-instance", "domain-instance.json"),
    ):
        expected = f"lulu-workflow/lulu-design/templates/{filename}"
        assert compose[key] == expected
        assert (skill_root / expected.split("/", 1)[1]).is_file(), key
    form = json.loads(
        (skill_root / "lulu-design/templates/section-form-registry.json").read_text(
            encoding="utf-8"
        )
    )
    assert form["sections"]["IF"]["reading_axis"] == (
        "address → named_faces → exercise"
    )


def test_design_k0b_profile_has_no_display_layer_flag() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    assert profile["pipeline"]["inductive"] is True
    assert "display_layer" not in profile.get("pipeline", {})
    assert "outline-registry" not in (profile.get("framework_templates") or {})
