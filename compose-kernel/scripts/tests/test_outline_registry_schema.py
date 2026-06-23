#!/usr/bin/env python3
"""Tests for outline_registry_schema.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from outline_registry_schema import (  # noqa: E402
    get_schema,
    load_outline_registry,
    normalize_outline_registry,
    validate_outline_registry,
    validate_outline_section_alignment,
)
from test_template_data import OUTLINE_REGISTRY_FEATURE  # noqa: E402


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
    assert loaded["outline_order"] == ["OV", "BD", "DS", "PL", "VF"]
    intent_map = {
        intent: block
        for block in loaded["outline_order"]
        for intent in loaded["blocks"][block]["intents"]
    }
    assert intent_map["CTX"] == "OV"
    assert intent_map["SC"] == "BD"
    assert intent_map["T"] == "PL"
    assert intent_map["VF"] == "VF"
    assert len(intent_map) == 10


def test_normalize_preserves_guidance_and_contract():
    loaded = normalize_outline_registry(OUTLINE_REGISTRY_FEATURE)
    pl = loaded["blocks"]["PL"]
    assert pl["guidance"] == "Execution thread."
    assert pl["contract"]["required"] == [
        "SK opens with Execution arc lead-in before the phase table"
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


def test_validate_rejects_invalid_contract():
    payload = dict(OUTLINE_REGISTRY_FEATURE)
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
            "NG",
            "I",
            "AR",
            "KD",
            "SK",
            "T",
            "VF",
        ],
        "document_preamble": "# Test",
        "sections": {key: {"heading": key, "intent": "x"} for key in [
            "CTX", "GO", "SC", "NG", "I", "AR", "KD", "SK", "T", "VF",
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
