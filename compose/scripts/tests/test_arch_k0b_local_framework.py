#!/usr/bin/env python3
"""K0b: lulu-arch section presence (skill-builtin section-registry SSOT)."""

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

from framework_template_sources import tech_arch_section_registry  # noqa: E402
from section_registry_schema import (  # noqa: E402
    normalize_section_registry,
    validate_section_registry,
)

_PROFILE = _REPO /  "lulu-arch" / "compose-profile.json"
_DIMENSION_DEF = (
    _REPO /  "lulu-arch" / "dimension-defs" / "arch-quality.json"
)
_METHOD = _REPO /  "lulu-arch" / "eval" / "methods" / "arch-quality.md"
_SOT = _REPO /  "lulu-arch" / "eval" / "sots" / "arch-quality.md"

def test_arch_k0b_section_registry_supply_and_remap() -> None:
    data = tech_arch_section_registry()
    assert validate_section_registry(data) == []
    normalized = normalize_section_registry(data)
    for key in normalized["section_order"]:
        expected = "none" if key == "OQ" else "ask"
        assert normalized["sections"][key]["supply"] == expected
    assert normalized["sections"]["FD"]["relations"]["SH"] == "operationalize"
    assert "attach_to" not in json.dumps(normalized["sections"]["FD"]["relations"])
    assert normalized["sections"]["KD"]["relations"]["SH"] == "instantiate"


def test_arch_k0b_profile_uses_direct_template_refs() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    compose = profile["framework_templates"]
    for key, filename in (
        ("section-registry", "section-registry.json"),
        ("section-form-registry", "section-form-registry.json"),
        ("section-kw-criteria", "section-kw-criteria.md"),
        ("role-instance", "role-instance.json"),
        ("domain-instance", "domain-instance.json"),
    ):
        expected = f"lulu-workflow/lulu-arch/templates/{filename}"
        assert compose[key] == expected
        assert (_REPO / expected.split("/", 1)[1]).is_file(), key

    dimension = json.loads(_DIMENSION_DEF.read_text(encoding="utf-8"))
    assert dimension["method"]["ref"] == "lulu-workflow/lulu-arch/eval/methods/arch-quality.md"
    assert dimension["sots"] == [
        {
            "ref": "lulu-workflow/lulu-arch/eval/sots/arch-quality.md",
        },
    ]
    assert _METHOD.is_file()
    assert _SOT.is_file()


def test_arch_k0b_profile_has_no_display_layer_flag() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    assert profile["pipeline"]["inductive"] is False
    assert "display_layer" not in profile.get("pipeline", {})
    assert "outline-registry" not in (profile.get("framework_templates") or {})
