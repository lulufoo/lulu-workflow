#!/usr/bin/env python3
"""Tests for section-registry facet seed helpers."""

from __future__ import annotations

from typing import Any

import pytest

import bootstrap  # noqa: F401

from section_registry_schema import validate_facets_list  # noqa: E402

_OPS_REGISTRY = {
    "version": "1",
    "section_order": ["I", "OPS"],
    "document_preamble": "test",
    "sections": {
        "I": {
            "heading": "Intent",
            "intent": "intent only",
            "upstream": [],
            "relations": {},
        },
        "OPS": {
            "heading": "Ops",
            "intent": "operability",
            "upstream": [],
            "relations": {},
            "facets": [
                "runtime degradation",
                "steady-state rollback",
            ],
        },
    },
}


def _parse_section_registry_facets(data: dict[str, Any]) -> dict[str, list[str]]:
    sections = data.get("sections")
    assert isinstance(sections, dict)
    out: dict[str, list[str]] = {}
    for key, entry in sections.items():
        if not isinstance(entry, dict) or "facets" not in entry:
            continue
        lens = str(key).strip().upper()
        out[lens] = validate_facets_list(entry.get("facets"), lens=lens)
    return out


def test_parse_ops_seeds_only():
    reg = _parse_section_registry_facets(_OPS_REGISTRY)
    assert "I" not in reg
    assert reg["OPS"] == [
        "runtime degradation",
        "steady-state rollback",
    ]


def test_rejects_object_shaped_facets():
    with pytest.raises(ValueError, match="non-empty string"):
        validate_facets_list(
            [{"id": "runtime_degradation", "required": True}],
            lens="OPS",
        )


def test_rejects_empty_string():
    with pytest.raises(ValueError, match="non-empty string"):
        validate_facets_list(["runtime degradation", "  "], lens="OPS")


def test_parse_round_trip_same_seeds():
    loaded = _parse_section_registry_facets(_OPS_REGISTRY)
    assert loaded["OPS"][0] == "runtime degradation"
