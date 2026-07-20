#!/usr/bin/env python3
"""K0b: lulu-arch section presence (upstream framework SSOT)."""

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

from framework_template_sources import tech_arch_section_registry  # noqa: E402
from section_registry_schema import (  # noqa: E402
    normalize_section_registry,
    validate_section_registry,
)

_SKILL_CONFIG = (
    _REPO / "skill-config" / "lulu-dev-workflow" / "stages" / "lulu-arch.json"
)
_PROFILE = _REPO / "lulu-dev-workflow" / "lulu-arch" / "compose-profile.json"
_GH_ARCH = (
    "https://github.com/lulufoo/lulu-workflow-framework/blob/main/"
    "lulu-dev-workflow/template/arch/"
)


def test_arch_k0b_section_registry_presence_and_remap() -> None:
    data = tech_arch_section_registry()
    assert validate_section_registry(data) == []
    normalized = normalize_section_registry(data)
    for key in normalized["section_order"]:
        expected = "optional" if key == "OQ" else "required"
        assert normalized["sections"][key]["presence"] == expected
    assert normalized["sections"]["FD"]["relations"]["SH"] == "operationalize"
    assert "attach_to" not in json.dumps(normalized["sections"]["FD"]["relations"])
    assert normalized["sections"]["KD"]["relations"]["SH"] == "instantiate"


def test_arch_k0b_skill_config_points_upstream() -> None:
    cfg = json.loads(_SKILL_CONFIG.read_text(encoding="utf-8"))
    compose = cfg["compose"]
    assert compose["tat_section_registry_url"] == (
        f"{_GH_ARCH}tech-arch-topic-section-registry.json"
    )
    for remote_key in (
        "tat_section_form_registry_url",
        "tat_section_kw_criteria_url",
        "tat_topic_role_instance_url",
        "tat_topic_domain_instance_url",
    ):
        assert compose[remote_key].startswith("https://"), remote_key
    assert cfg["eval"]["tat_arch_quality_framework_url"].startswith("https://")


def test_arch_k0b_profile_has_no_display_layer_flag() -> None:
    profile = json.loads(_PROFILE.read_text(encoding="utf-8"))
    assert profile["drafting"]["inductive"] is False
    assert "display_layer" not in profile.get("drafting", {})
    assert "outline-registry" not in (profile.get("framework_templates") or {})
