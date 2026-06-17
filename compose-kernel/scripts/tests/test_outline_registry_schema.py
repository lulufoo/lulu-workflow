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
    validate_outline_registry,
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
    assert intent_map["T"] == "PL"
    assert intent_map["VF"] == "VF"
    assert len(intent_map) == 10


def test_validate_rejects_duplicate_intent():
    payload = dict(OUTLINE_REGISTRY_FEATURE)
    payload["blocks"] = dict(payload["blocks"])
    payload["blocks"]["VF"] = dict(payload["blocks"]["VF"])
    payload["blocks"]["VF"]["intents"] = ["VF", "CTX"]
    errors = validate_outline_registry(payload)
    assert any("more than one outline block" in err for err in errors)


def test_validate_requires_feature_cycle_type_when_present():
    payload = dict(OUTLINE_REGISTRY_FEATURE)
    payload["cycle_type"] = "topic"
    errors = validate_outline_registry(payload)
    assert any("cycle_type" in err for err in errors)
