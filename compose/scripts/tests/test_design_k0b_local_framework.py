#!/usr/bin/env python3
"""K0b: lulu-design section presence (upstream framework SSOT)."""

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

from framework_template_sources import tech_design_section_registry  # noqa: E402
from section_registry_schema import (  # noqa: E402
    normalize_section_registry,
    validate_section_registry,
)

_SKILL_CONFIG = (
    _REPO / "skill-config" / "lulu-dev-workflow" / "stages" / "lulu-design.json"
)
_PROFILE = _REPO / "lulu-dev-workflow" / "lulu-design" / "compose-profile.json"
_GH_DESIGN = (
    "https://github.com/lulufoo/lulu-workflow-framework/blob/main/"
    "lulu-dev-workflow/template/design/"
)


def test_design_k0b_section_registry_has_presence() -> None:
    from section_registry_schema import lens_key_sequence

    data = tech_design_section_registry()
    assert validate_section_registry(data) == []
    normalized = normalize_section_registry(data)
    keys = lens_key_sequence(normalized)
    assert "section_order" not in normalized
    for key in keys:
        presence = normalized["sections"][key]["presence"]
        assert presence in {"required", "optional"}
    # Lens V2 optional seams / risks / deps (CMP/OD removed)
    assert normalized["sections"]["SEAM"]["presence"] == "optional"
    assert normalized["sections"]["RISK"]["presence"] == "optional"
    assert normalized["sections"]["DEP"]["presence"] == "optional"
    assert "CMP" not in keys
    assert "GOAL" in keys and "SCOPE" in keys and "DECISION" in keys


def test_design_k0b_skill_config_points_upstream() -> None:
    cfg = json.loads(_SKILL_CONFIG.read_text(encoding="utf-8"))
    compose = cfg["compose"]
    assert compose["tdt_section_registry_url"] == (
        f"{_GH_DESIGN}42-tech-design-section-registry.json"
    )
    assert compose["tdt_section_form_registry_url"] == (
        "lulu-dev-workflow/lulu-design/templates/section-form-registry.json"
    )
    # Prefix = skill runtime root; remainder is under installed/source skill tree.
    skill_root = _REPO / "lulu-dev-workflow"
    rel = compose["tdt_section_form_registry_url"].split("/", 1)[1]
    form_path = skill_root / rel
    assert form_path.is_file()
    form = json.loads(form_path.read_text(encoding="utf-8"))
    assert form["sections"]["IF"]["reading_axis"] == (
        "address → named_faces → exercise"
    )


def test_design_k0b_profile_has_no_display_layer_flag() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    assert profile["pipeline"]["inductive"] is True
    assert "display_layer" not in profile.get("pipeline", {})
    assert "outline-registry" not in (profile.get("framework_templates") or {})
