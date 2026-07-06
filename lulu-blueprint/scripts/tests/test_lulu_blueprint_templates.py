#!/usr/bin/env python3
"""Schema validation for lulu-blueprint compose templates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_REGISTRY_DIR = (
    _WORKFLOW_ROOT / "compose" / "scripts" / "schema" / "section" / "registry"
)
_TEMPLATES = _WORKFLOW_ROOT / "lulu-blueprint" / "templates"

for p in (_REGISTRY_DIR, _WORKFLOW_ROOT / "compose" / "scripts" / "core"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from section_form_registry_schema import (  # noqa: E402
    normalize_section_form_registry,
    validate_section_form_alignment,
    validate_section_form_registry,
)
from section_registry_schema import validate_section_registry  # noqa: E402


@pytest.fixture
def section_registry() -> dict:
    return json.loads(
        (
            _TEMPLATES / "product-blueprint-topic-section-registry.json"
        ).read_text(encoding="utf-8"),
    )


@pytest.fixture
def section_form_registry() -> dict:
    return json.loads(
        (
            _TEMPLATES / "product-blueprint-topic-section-form-registry.json"
        ).read_text(encoding="utf-8"),
    )


def test_section_registry_schema(section_registry: dict) -> None:
    assert validate_section_registry(section_registry) == []


def test_section_form_registry_schema(section_form_registry: dict) -> None:
    assert validate_section_form_registry(section_form_registry) == []


def test_section_form_alignment(section_registry: dict, section_form_registry: dict) -> None:
    form = normalize_section_form_registry(section_form_registry)
    assert validate_section_form_alignment(form, section_registry) == []


def test_section_order_matches_across_registries(
    section_registry: dict,
    section_form_registry: dict,
) -> None:
    assert section_registry["section_order"] == section_form_registry["section_order"]

    outline = json.loads(
        (
            _TEMPLATES / "product-blueprint-topic-outline-registry.json"
        ).read_text(encoding="utf-8"),
    )
    assert outline["outline_order"] == section_registry["section_order"]
