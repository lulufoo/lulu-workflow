#!/usr/bin/env python3
"""K0b: lulu-blueprint section presence (skill-builtin section-registry SSOT)."""

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

from framework_template_sources import product_blueprint_section_registry  # noqa: E402
from section_registry_schema import (  # noqa: E402
    normalize_section_registry,
    validate_section_registry,
)

_PROFILE = _REPO /  "lulu-blueprint" / "compose-profile.json"
_DIMENSION_DEF = (
    _REPO
   
    / "lulu-blueprint"
    / "dimension-defs"
    / "blueprint-quality.json"
)
_METHOD = (
    _REPO
   
    / "lulu-blueprint"
    / "eval"
    / "methods"
    / "blueprint-quality.md"
)
_SOT = (
    _REPO
   
    / "lulu-blueprint"
    / "eval"
    / "sots"
    / "blueprint-quality.md"
)

def test_blueprint_k0b_section_registry_presence_and_edges() -> None:
    data = product_blueprint_section_registry()
    assert validate_section_registry(data) == []
    normalized = normalize_section_registry(data)
    for key in normalized["section_order"]:
        expected = "optional" if key == "OQ" else "required"
        assert normalized["sections"][key]["presence"] == expected
    assert normalized["sections"]["PR"]["relations"]["PS"] == "instantiate"


def test_blueprint_k0b_profile_uses_direct_template_refs() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    compose = profile["framework_templates"]
    for key, filename in (
        ("section-registry", "section-registry.json"),
        ("section-form-registry", "section-form-registry.json"),
        ("section-kw-criteria", "section-kw-criteria.md"),
        ("role-instance", "role-instance.json"),
        ("domain-instance", "domain-instance.json"),
    ):
        expected = f"lulu-workflow/lulu-blueprint/templates/{filename}"
        assert compose[key] == expected
        assert (_REPO / expected.split("/", 1)[1]).is_file(), key

    dimension = json.loads(_DIMENSION_DEF.read_text(encoding="utf-8"))
    assert dimension["method"]["ref"] == (
        "lulu-workflow/lulu-blueprint/eval/methods/blueprint-quality.md"
    )
    assert dimension["sots"] == [
        {
            "ref": "lulu-workflow/lulu-blueprint/eval/sots/blueprint-quality.md",
        },
    ]
    assert _METHOD.is_file()
    assert _SOT.is_file()


def test_blueprint_k0b_profile_has_no_display_layer_flag() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    assert profile["pipeline"]["inductive"] is False
    assert "display_layer" not in profile.get("pipeline", {})
    assert "outline-registry" not in (profile.get("framework_templates") or {})
