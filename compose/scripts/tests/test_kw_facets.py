#!/usr/bin/env python3
"""Tests for section-registry facet seed helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
sys.path.insert(0, str(_INDUCTIVE_DIR))

from kw_facets import (  # noqa: E402
    parse_section_registry_facets,
    validate_facets_list,
)

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


def test_parse_ops_seeds_only():
    reg = parse_section_registry_facets(_OPS_REGISTRY)
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
    loaded = parse_section_registry_facets(_OPS_REGISTRY)
    assert loaded["OPS"][0] == "runtime degradation"
