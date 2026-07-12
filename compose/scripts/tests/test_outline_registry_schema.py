#!/usr/bin/env python3
"""Tests for outline_registry_schema.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from outline_registry_schema import (  # noqa: E402
    candidate_anchor_lenses,
    candidate_ids,
    get_schema,
    load_outline_registry,
    normalize_outline_registry,
    outline_intent_map,
    outline_order,
    validate_outline_candidates_alignment,
    validate_outline_registry,
    validate_outline_section_alignment,
)
from section_registry_schema import normalize_section_registry  # noqa: E402
from test_template_data import OUTLINE_REGISTRY_FEATURE, OUTLINE_REGISTRY_WITH_BLOCK_FORM  # noqa: E402
from framework_template_sources import (  # noqa: E402
    tech_design_outline_registry,
    tech_design_section_registry,
)

TECH_DESIGN_OUTLINE = tech_design_outline_registry()
TECH_DESIGN_SECTION = tech_design_section_registry()


@pytest.fixture
def outline_path(tmp_path: Path) -> Path:
    path = tmp_path / "outline-registry.json"
    path.write_text(json.dumps(OUTLINE_REGISTRY_FEATURE), encoding="utf-8")
    return path


def test_get_schema_includes_outline_order():
    fields = {entry["field"] for entry in get_schema()}
    assert "outline_order" in fields
    assert "blocks" in fields


def test_outline_order_and_intent_map(outline_path: Path):
    loaded = load_outline_registry(outline_path)
    assert loaded["outline_order"] == ["OV", "BD", "DS", "IV", "PL", "VF"]
    intent_map = {
        intent: block
        for block in loaded["outline_order"]
        for intent in loaded["blocks"][block]["intents"]
    }
    assert intent_map["CTX"] == "OV"
    assert intent_map["SC"] == "BD"
    assert intent_map["I"] == "IV"
    assert intent_map["T"] == "PL"
    assert intent_map["VF"] == "VF"
    assert len(intent_map) == 9


def test_normalize_preserves_guidance_and_contract():
    loaded = normalize_outline_registry(OUTLINE_REGISTRY_WITH_BLOCK_FORM)
    pl = loaded["blocks"]["PL"]
    assert pl["guidance"] == "Single execution thread: SK H3 before T H3."
    assert pl["contract"]["required"] == [
        "SK opens with Execution arc lead-in before the phase table",
    ]
    assert pl["contract"]["forbidden"] == [
        "Prose-only task lists without checkbox steps"
    ]


def test_validate_rejects_reader_note():
    payload = {
        "version": "1",
        "outline_order": ["OV"],
        "blocks": {
            "OV": {
                "heading": "Overview",
                "intents": ["CTX"],
                "reader_note": "Legacy note.",
            },
        },
    }
    errors = validate_outline_registry(payload)
    assert any("reader_note is not supported" in err for err in errors)


def test_validate_rejects_document_preamble_addon():
    payload = dict(OUTLINE_REGISTRY_FEATURE)
    payload["document_preamble_addon"] = "legacy addon"
    errors = validate_outline_registry(payload)
    assert any("document_preamble_addon is not supported" in err for err in errors)


def test_validate_rejects_invalid_contract():
    payload = dict(OUTLINE_REGISTRY_WITH_BLOCK_FORM)
    payload["blocks"] = dict(payload["blocks"])
    payload["blocks"]["PL"] = dict(payload["blocks"]["PL"])
    payload["blocks"]["PL"]["contract"] = {"required": [""]}
    errors = validate_outline_registry(payload)
    assert any("contract.required[0]" in err for err in errors)


def test_validate_rejects_duplicate_intent():
    payload = dict(OUTLINE_REGISTRY_FEATURE)
    payload["blocks"] = dict(payload["blocks"])
    payload["blocks"]["VF"] = dict(payload["blocks"]["VF"])
    payload["blocks"]["VF"]["intents"] = ["VF", "CTX"]
    errors = validate_outline_registry(payload)
    assert any("more than one outline block" in err for err in errors)


def test_validate_outline_section_alignment():
    outline = normalize_outline_registry(OUTLINE_REGISTRY_FEATURE)
    section_registry = {
        "version": "1",
        "section_order": [
            "CTX",
            "GO",
            "SC",
            "I",
            "AR",
            "KD",
            "SK",
            "T",
            "VF",
        ],
        "document_preamble": "# Test",
        "sections": {key: {"heading": key, "intent": "x"} for key in [
            "CTX", "GO", "SC", "I", "AR", "KD", "SK", "T", "VF",
        ]},
    }
    assert validate_outline_section_alignment(outline, section_registry) == []


def test_validate_outline_section_alignment_reports_mismatch():
    outline = normalize_outline_registry(OUTLINE_REGISTRY_FEATURE)
    section_registry = {"section_order": ["CTX", "GO"], "sections": {}}
    errors = validate_outline_section_alignment(outline, section_registry)
    assert any("not listed in section_order" in err for err in errors)
    section_registry_extra = {
        "section_order": ["CTX", "GO", "MISSING"],
        "sections": {},
    }
    errors = validate_outline_section_alignment(outline, section_registry_extra)
    assert any("missing from outline blocks intents" in err for err in errors)


def test_validate_slim_outline():
    errors = validate_outline_registry(TECH_DESIGN_OUTLINE)
    assert errors == []


def test_tech_design_outline_section_alignment():
    outline = normalize_outline_registry(TECH_DESIGN_OUTLINE)
    section = normalize_section_registry(TECH_DESIGN_SECTION)
    assert validate_outline_section_alignment(outline, section) == []


def test_normalize_slim_outline_heading_intents_only():
    loaded = normalize_outline_registry(TECH_DESIGN_OUTLINE)
    assert loaded["blocks"]["SI"]["intents"] == ["CTX", "GO"]
    assert "assembly" not in loaded["blocks"]["SI"]
    assert "guidance" not in loaded["blocks"]["SH"]


def test_validate_rejects_assembly():
    payload = {
        "version": "1",
        "outline_order": ["SI"],
        "blocks": {
            "SI": {
                "heading": "Situation & Intent",
                "intents": ["CTX", "GO"],
                "assembly": {"forbidden": ["tables"]},
            },
        },
    }
    errors = validate_outline_registry(payload)
    assert any("assembly is not supported" in err for err in errors)


def test_validate_slim_block_heading_intents_only():
    payload = {
        "version": "1",
        "outline_order": ["SH"],
        "blocks": {
            "SH": {
                "heading": "Solution Shape",
                "intents": ["ST"],
            },
        },
    }
    assert validate_outline_registry(payload) == []


_VALID_CANDIDATES_PAYLOAD = {
    "version": "1",
    "candidates": [
        {"block": "cand-CTX", "anchor_lenses": ["CTX"]},
        {"block": "cand-AR", "anchor_lenses": ["AR", "SC"]},
    ],
    "rules": ["空可选视角→删", "瘦→并"],
}


def test_validate_candidates_shape_accepts_valid_payload():
    assert validate_outline_registry(_VALID_CANDIDATES_PAYLOAD) == []


def test_validate_candidates_shape_rejects_coexistence_with_legacy_fields():
    payload = dict(_VALID_CANDIDATES_PAYLOAD)
    payload["outline_order"] = ["OV"]
    errors = validate_outline_registry(payload)
    assert any("cannot coexist with outline_order/blocks" in err for err in errors)


def test_validate_rejects_orphan_rules_without_candidates():
    payload = {
        "version": "1",
        "outline_order": ["OV"],
        "blocks": {"OV": {"heading": "Overview", "intents": ["CTX"]}},
        "rules": ["空可选视角→删"],
    }
    errors = validate_outline_registry(payload)
    assert any("rules without candidates is not supported" in err for err in errors)


def test_validate_candidates_shape_rejects_document_preamble_addon():
    payload = dict(_VALID_CANDIDATES_PAYLOAD)
    payload["document_preamble_addon"] = "legacy addon"
    errors = validate_outline_registry(payload)
    assert any("unexpected top-level fields" in err for err in errors)


def test_validate_candidates_shape_rejects_duplicate_block():
    payload = {
        "version": "1",
        "candidates": [
            {"block": "cand-AR", "anchor_lenses": ["AR"]},
            {"block": "cand-AR", "anchor_lenses": ["SC"]},
        ],
    }
    errors = validate_outline_registry(payload)
    assert any("block duplicate" in err for err in errors)


def test_validate_candidates_shape_rejects_empty_candidates():
    payload = {"version": "1", "candidates": []}
    errors = validate_outline_registry(payload)
    assert any("candidates must be a non-empty array" in err for err in errors)


def test_validate_candidates_shape_rejects_lowercase_anchor_lens():
    payload = {
        "version": "1",
        "candidates": [{"block": "cand-ar", "anchor_lenses": ["ar"]}],
    }
    errors = validate_outline_registry(payload)
    assert any("must be uppercase lens key" in err for err in errors)


def test_validate_candidates_shape_rejects_unknown_entry_field():
    payload = {
        "version": "1",
        "candidates": [{"block": "cand-AR", "anchor_lenses": ["AR"], "extra": 1}],
    }
    errors = validate_outline_registry(payload)
    assert any("unexpected fields" in err for err in errors)


def test_normalize_candidates_shape():
    normalized = normalize_outline_registry(_VALID_CANDIDATES_PAYLOAD)
    assert normalized == {
        "version": "1",
        "candidates": [
            {"block": "cand-CTX", "anchor_lenses": ["CTX"]},
            {"block": "cand-AR", "anchor_lenses": ["AR", "SC"]},
        ],
        "rules": ["空可选视角→删", "瘦→并"],
    }
    assert "outline_order" not in normalized
    assert "blocks" not in normalized


def test_validate_outline_candidates_alignment_passes_with_full_coverage():
    outline = normalize_outline_registry(_VALID_CANDIDATES_PAYLOAD)
    section_registry = {
        "section_order": ["CTX", "AR", "SC"],
        "sections": {
            "CTX": {"presence": "required"},
            "AR": {"presence": "required"},
            "SC": {"presence": "optional"},
        },
    }
    assert validate_outline_candidates_alignment(outline, section_registry) == []


def test_validate_outline_candidates_alignment_allows_optional_lens_with_no_candidate():
    outline = normalize_outline_registry(
        {"version": "1", "candidates": [{"block": "cand-CTX", "anchor_lenses": ["CTX"]}]},
    )
    section_registry = {
        "section_order": ["CTX", "NG"],
        "sections": {"CTX": {"presence": "required"}, "NG": {"presence": "optional"}},
    }
    assert validate_outline_candidates_alignment(outline, section_registry) == []


def test_validate_outline_candidates_alignment_rejects_uncovered_required_lens():
    outline = normalize_outline_registry(
        {"version": "1", "candidates": [{"block": "cand-CTX", "anchor_lenses": ["CTX"]}]},
    )
    section_registry = {
        "section_order": ["CTX", "AR"],
        "sections": {"CTX": {"presence": "required"}, "AR": {"presence": "required"}},
    }
    errors = validate_outline_candidates_alignment(outline, section_registry)
    assert any("required lens 'AR' has no anchoring candidate" in err for err in errors)


def test_validate_outline_candidates_alignment_rejects_unknown_anchor_lens():
    outline = normalize_outline_registry(
        {"version": "1", "candidates": [{"block": "cand-ZZ", "anchor_lenses": ["ZZ"]}]},
    )
    section_registry = {"section_order": ["CTX"], "sections": {"CTX": {"presence": "required"}}}
    errors = validate_outline_candidates_alignment(outline, section_registry)
    assert any("not in section_order" in err for err in errors)


def test_candidate_accessors(monkeypatch):
    import outline_registry_schema as schema_mod  # noqa: E402

    fake_registry = normalize_outline_registry(_VALID_CANDIDATES_PAYLOAD)
    monkeypatch.setattr(schema_mod, "_active_outline", lambda project_root=None: fake_registry)
    assert candidate_ids() == ("cand-CTX", "cand-AR")
    assert candidate_anchor_lenses() == {"cand-CTX": ["CTX"], "cand-AR": ["AR", "SC"]}


def test_legacy_accessors_hard_error_on_candidates_shape(monkeypatch):
    import outline_registry_schema as schema_mod  # noqa: E402

    fake_registry = normalize_outline_registry(_VALID_CANDIDATES_PAYLOAD)
    monkeypatch.setattr(schema_mod, "_active_outline", lambda project_root=None: fake_registry)
    with pytest.raises(ValueError, match="candidates-shaped"):
        outline_order()
    with pytest.raises(ValueError, match="candidates-shaped"):
        outline_intent_map()


def test_candidate_accessors_hard_error_on_legacy_shape(monkeypatch):
    import outline_registry_schema as schema_mod  # noqa: E402

    fake_registry = normalize_outline_registry(OUTLINE_REGISTRY_FEATURE)
    monkeypatch.setattr(schema_mod, "_active_outline", lambda project_root=None: fake_registry)
    with pytest.raises(ValueError, match="legacy blocks-shaped"):
        candidate_ids()
    with pytest.raises(ValueError, match="legacy blocks-shaped"):
        candidate_anchor_lenses()


def test_candidates_dispatch_treats_explicit_null_as_candidates_shape():
    payload = {
        "version": "1",
        "candidates": None,
        "outline_order": ["OV"],
        "blocks": {"OV": {"heading": "Overview", "intents": ["CTX"]}},
    }
    errors = validate_outline_registry(payload)
    assert any("cannot coexist with outline_order/blocks" in err for err in errors)
    assert any("candidates must be a non-empty array" in err for err in errors)


def test_validate_candidates_shape_preserves_block_case():
    payload = {
        "version": "1",
        "candidates": [{"block": "Cand-Mixed", "anchor_lenses": ["AR"]}],
    }
    assert validate_outline_registry(payload) == []
    normalized = normalize_outline_registry(payload)
    assert normalized["candidates"][0]["block"] == "Cand-Mixed"


def test_validate_candidates_shape_rejects_duplicate_anchor_lens_in_one_entry():
    payload = {
        "version": "1",
        "candidates": [{"block": "cand-AR", "anchor_lenses": ["AR", "ar"]}],
    }
    errors = validate_outline_registry(payload)
    assert any("anchor_lenses duplicate" in err for err in errors)


def test_validate_outline_candidates_alignment_treats_null_presence_as_required():
    outline = normalize_outline_registry(
        {"version": "1", "candidates": [{"block": "cand-CTX", "anchor_lenses": ["CTX"]}]},
    )
    section_registry = {
        "section_order": ["CTX", "AR"],
        "sections": {"CTX": {"presence": "required"}, "AR": {"presence": None}},
    }
    errors = validate_outline_candidates_alignment(outline, section_registry)
    assert any("required lens 'AR' has no anchoring candidate" in err for err in errors)


def test_load_outline_registry_round_trips_candidates_shape(tmp_path: Path):
    path = tmp_path / "outline-registry.json"
    path.write_text(json.dumps(_VALID_CANDIDATES_PAYLOAD), encoding="utf-8")
    loaded = load_outline_registry(path)
    assert loaded["candidates"] == [
        {"block": "cand-CTX", "anchor_lenses": ["CTX"]},
        {"block": "cand-AR", "anchor_lenses": ["AR", "SC"]},
    ]
    assert "outline_order" not in loaded


def test_get_schema_marks_legacy_fields_optional():
    fields = {entry["field"]: entry for entry in get_schema()}
    assert fields["outline_order"]["required"] is False
    assert fields["blocks"]["required"] is False


def test_get_schema_includes_candidates_and_rules():
    fields = {entry["field"] for entry in get_schema()}
    assert "candidates" in fields
    assert "rules" in fields


def test_validate_rejects_contract_without_guidance():
    payload = {
        "version": "1",
        "outline_order": ["SH"],
        "blocks": {
            "SH": {
                "heading": "Solution Shape",
                "intents": ["ST"],
                "contract": {"required": ["x"], "forbidden": []},
            },
        },
    }
    errors = validate_outline_registry(payload)
    assert any("contract without guidance" in err for err in errors)
