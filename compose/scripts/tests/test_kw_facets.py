#!/usr/bin/env python3
"""Tests for section-registry facet helpers."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
sys.path.insert(0, str(_INDUCTIVE_DIR))

from kw_facets import (  # noqa: E402
    find_active_open_collision,
    materialize_section_registry,
    parse_section_registry_facets,
    section_registry_path,
    silence_must_facets,
    validate_facet_id_for_lens,
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
                {
                    "id": "runtime_degradation",
                    "desc": "Runtime degradation stance.",
                    "required": True,
                },
                {
                    "id": "steady_state_rollback",
                    "desc": "Steady-state rollback stance.",
                    "required": True,
                },
                {
                    "id": "cutover_migration_repair",
                    "desc": "Cutover migration repair stance.",
                    "required": True,
                },
                {
                    "id": "other",
                    "desc": "Unclassified sides.",
                    "required": False,
                },
            ],
        },
    },
}


def test_parse_ops_facets_only():
    reg = parse_section_registry_facets(_OPS_REGISTRY)
    assert "I" not in reg
    assert "OPS" in reg
    ids = {f["id"] for f in reg["OPS"]}
    assert ids == {
        "runtime_degradation",
        "steady_state_rollback",
        "cutover_migration_repair",
        "other",
    }
    other = next(f for f in reg["OPS"] if f["id"] == "other")
    assert other["required"] is False
    assert other["desc"]


def test_other_must_be_optional():
    bad = {
        "sections": {
            "OPS": {
                "facets": [
                    {
                        "id": "other",
                        "desc": "x",
                        "required": True,
                    }
                ]
            }
        }
    }
    with pytest.raises(ValueError, match="required=false"):
        parse_section_registry_facets(bad)


def test_rejects_per_facet_kw():
    bad = {
        "sections": {
            "OPS": {
                "facets": [
                    {
                        "id": "other",
                        "desc": "x",
                        "required": False,
                        "kw": 1,
                    }
                ]
            }
        }
    }
    with pytest.raises(ValueError, match="per-facet kw"):
        parse_section_registry_facets(bad)


def test_requires_desc():
    bad = {
        "sections": {
            "OPS": {
                "facets": [
                    {"id": "other", "required": False},
                ]
            }
        }
    }
    with pytest.raises(ValueError, match="desc"):
        parse_section_registry_facets(bad)


def test_validate_facet_rules():
    reg = parse_section_registry_facets(_OPS_REGISTRY)
    assert validate_facet_id_for_lens(None, lens="I", registry=reg) == []
    assert validate_facet_id_for_lens("x", lens="I", registry=reg)
    assert validate_facet_id_for_lens(None, lens="OPS", registry=reg)
    assert (
        validate_facet_id_for_lens(
            "runtime_degradation",
            lens="OPS",
            registry=reg,
        )
        == []
    )


def test_silence_and_receipts():
    reg = parse_section_registry_facets(_OPS_REGISTRY)
    facets = reg["OPS"]
    missing = silence_must_facets(
        lens="OPS",
        facets=facets,
        opens=[],
        facts=[
            {
                "id": "F-1",
                "text": "migration only",
                "lens_tags": ["OPS"],
                "facet_id": "cutover_migration_repair",
            }
        ],
    )
    assert set(missing) == {"runtime_degradation", "steady_state_rollback"}

    missing2 = silence_must_facets(
        lens="OPS",
        facets=facets,
        opens=[
            {
                "id": "O-1",
                "status": "open",
                "detected_under": "OPS",
                "facet_id": "runtime_degradation",
            }
        ],
        facts=[
            {
                "id": "F-1",
                "text": "migration",
                "lens_tags": ["OPS"],
                "facet_id": "cutover_migration_repair",
            },
            {
                "id": "F-2",
                "text": "no steady-state rollback protocol",
                "lens_tags": ["OPS"],
                "facet_id": "steady_state_rollback",
            },
        ],
    )
    assert missing2 == []


def test_materialize_section_registry(tmp_path):
    path = materialize_section_registry(tmp_path, _OPS_REGISTRY)
    assert path == section_registry_path(tmp_path)
    assert path.is_file()
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert "OPS" in parse_section_registry_facets(loaded)


def test_active_open_collision():
    opens = [
        {
            "id": "O-1",
            "status": "open",
            "detected_under": "OPS",
            "kw": 1,
            "facet_id": "other",
        },
        {
            "id": "O-2",
            "status": "settled",
            "detected_under": "OPS",
            "kw": 1,
            "facet_id": "other",
            "resolved_by": ["F-1"],
        },
    ]
    hit = find_active_open_collision(
        opens,
        detected_under="OPS",
        kw=1,
        facet_id="other",
    )
    assert hit is not None and hit["id"] == "O-1"
