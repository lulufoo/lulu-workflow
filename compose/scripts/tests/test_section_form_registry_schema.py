#!/usr/bin/env python3
"""Tests for section_form_registry_schema.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from section_form_registry_schema import (  # noqa: E402
    get_schema,
    load_section_form_registry,
    merge_section_form_into_registry,
    normalize_section_form_registry,
    validate_section_form_alignment,
    validate_section_form_registry,
)
from section_registry_schema import normalize_section_registry  # noqa: E402
from framework_template_sources import (  # noqa: E402
    product_spec_section_form_registry,
    tech_design_section_form_registry,
    tech_design_section_registry,
)

TECH_DESIGN_INTENT = tech_design_section_registry()
TECH_DESIGN_FORM = tech_design_section_form_registry()
PRODUCT_SPEC_FORM = product_spec_section_form_registry()


def test_get_schema_includes_section_order():
    fields = {entry["field"] for entry in get_schema()}
    assert "section_order" in fields
    assert "sections" in fields


def test_validate_tech_design_form_registry():
    assert validate_section_form_registry(TECH_DESIGN_FORM) == []


def test_normalize_keeps_reading_axis_and_when():
    form = normalize_section_form_registry(TECH_DESIGN_FORM)
    if_entry = form["sections"]["IF"]
    assert if_entry["reading_axis"] == "address → named_faces → exercise"
    when_vals = [a["when"] for a in if_entry["presentation"]["allowed"]]
    assert when_vals
    assert all(isinstance(w, str) and w.strip() for w in when_vals)
    assert form["sections"]["CTX"]["reading_axis"] == (
        "frame → pressure → unresolved"
    )


def test_validate_form_alignment():
    intent = normalize_section_registry(TECH_DESIGN_INTENT)
    form = normalize_section_form_registry(TECH_DESIGN_FORM)
    assert validate_section_form_alignment(form, intent) == []


def test_product_spec_form_unavailable_until_upgraded():
    """Other stages remain on old form shape → hard-format validate fails."""
    errors = validate_section_form_registry(PRODUCT_SPEC_FORM)
    assert errors
    joined = "\n".join(errors)
    assert "reading_axis" in joined or "when" in joined or "legacy" in joined


def test_validate_rejects_intent_fields_in_form():
    payload = json.loads(json.dumps(TECH_DESIGN_FORM))
    payload["sections"]["CTX"]["intent"] = "leak"
    errors = validate_section_form_registry(payload)
    assert any("intent is not supported" in err for err in errors)


def test_validate_rejects_missing_reading_axis_key():
    payload = json.loads(json.dumps(TECH_DESIGN_FORM))
    del payload["sections"]["CTX"]["reading_axis"]
    errors = validate_section_form_registry(payload)
    assert any("reading_axis is required" in err for err in errors)


def test_validate_rejects_missing_when():
    payload = json.loads(json.dumps(TECH_DESIGN_FORM))
    allowed = payload["sections"]["CTX"]["presentation"]["allowed"]
    del allowed[0]["when"]
    errors = validate_section_form_registry(payload)
    assert any(".when must be a non-empty string" in err for err in errors)


def test_validate_rejects_mismatched_section_order():
    intent = normalize_section_registry(TECH_DESIGN_INTENT)
    form = normalize_section_form_registry(TECH_DESIGN_FORM)
    keys = list(form["sections"])
    if len(keys) < 2:
        raise AssertionError("expected at least two form sections")
    # Swap first two keys to break alignment while keeping membership.
    reordered = {keys[1]: form["sections"][keys[1]], keys[0]: form["sections"][keys[0]]}
    for k in keys[2:]:
        reordered[k] = form["sections"][k]
    form["sections"] = reordered
    form.pop("section_order", None)
    errors = validate_section_form_alignment(form, intent)
    assert any("must match section-registry" in err for err in errors)


def test_merge_section_form_into_registry():
    intent = normalize_section_registry(TECH_DESIGN_INTENT)
    form = normalize_section_form_registry(TECH_DESIGN_FORM)
    merged = merge_section_form_into_registry(intent, form)
    assert merged["sections"]["CTX"]["presentation"]["guidance"]
    assert merged["sections"]["CTX"]["reading_axis"] == (
        "frame → pressure → unresolved"
    )
    assert merged["sections"]["CTX"]["expression"]["required"]
    assert "presentation" not in intent["sections"]["CTX"]


def test_load_form_registry_with_alignment(tmp_path: Path):
    intent_path = tmp_path / "intent.json"
    form_path = tmp_path / "form.json"
    intent_path.write_text(json.dumps(TECH_DESIGN_INTENT), encoding="utf-8")
    form_path.write_text(json.dumps(TECH_DESIGN_FORM), encoding="utf-8")
    intent = normalize_section_registry(TECH_DESIGN_INTENT)
    loaded = load_section_form_registry(form_path, intent_registry=intent)
    assert loaded["sections"]["GOAL"]["expression"]["required"]
    assert "when" in loaded["sections"]["GOAL"]["presentation"]["allowed"][0]
