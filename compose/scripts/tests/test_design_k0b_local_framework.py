#!/usr/bin/env python3
"""K0b: lulu-design section presence (skill-builtin section-registry SSOT)."""

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
        "lulu-dev-workflow/lulu-design/templates/section-registry.json"
    )
    assert compose["tdt_section_form_registry_url"] == (
        "lulu-dev-workflow/lulu-design/templates/section-form-registry.json"
    )
    # Prefix = skill runtime root; remainder is under installed/source skill tree.
    skill_root = _REPO / "lulu-dev-workflow"
    for key in (
        "tdt_section_registry_url",
        "tdt_section_form_registry_url",
        "tdt_section_kw_criteria_url",
        "tdt_feature_role_instance_url",
        "tdt_feature_domain_instance_url",
    ):
        assert compose[key].startswith(
            "lulu-dev-workflow/lulu-design/templates/"
        ), key
        rel = compose[key].split("/", 1)[1]
        assert (skill_root / rel).is_file(), key
    # inductive scan criteria remains remote for now
    assert compose["tdt_inductive_scan_criteria_url"].startswith("https://")
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
