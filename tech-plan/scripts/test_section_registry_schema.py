#!/usr/bin/env python3
"""Tests for section_registry_schema.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from section_registry_schema import (  # noqa: E402
    document_preamble,
    initial_fill_results,
    load_section_registry,
    normalize_section,
    section_heading,
    section_keys,
    section_order,
    upstream_edges,
    validate_section_registry,
)
from section_dependency_schema import load_dependency_graph  # noqa: E402

_FIXTURE_REGISTRY = Path(__file__).resolve().parent / "test_fixtures" / "section-registry.json"


def _load_fixture_registry() -> dict:
    return load_section_registry(_FIXTURE_REGISTRY)


def test_section_order_and_keys():
    reg = _load_fixture_registry()
    assert section_order() == tuple(reg["section_order"])
    assert section_keys() == frozenset(reg["section_order"])


def test_normalize_section_aliases():
    reg = _load_fixture_registry()
    ng_key = reg["section_order"][1]
    assert normalize_section(ng_key) == ng_key
    assert normalize_section(reg["sections"][ng_key]["aliases"][0]) == ng_key
    assert normalize_section(reg["sections"][ng_key]["heading"]) == ng_key


def test_section_heading():
    reg = _load_fixture_registry()
    ng_key = reg["section_order"][1]
    assert section_heading(ng_key) == reg["sections"][ng_key]["heading"]


def test_document_preamble():
    preamble = document_preamble()
    assert "# {Feature Name} Tech Plan" in preamble
    assert "state-vector" not in preamble


def test_initial_fill_results():
    reg = _load_fixture_registry()
    fills = initial_fill_results()
    expected_headings = {reg["sections"][k]["heading"] for k in reg["section_order"]}
    assert set(fills) == expected_headings
    first_heading = reg["sections"][reg["section_order"][0]]["heading"]
    assert fills[first_heading]["content"] == ""
    assert fills[first_heading]["status"] == "X"


def test_upstream_edges_from_registry():
    reg = _load_fixture_registry()
    kd_key = reg["section_order"][3]
    graph = load_dependency_graph(_FIXTURE_REGISTRY)
    edges = upstream_edges(kd_key, graph)
    assert {e["upstream_section"] for e in edges} == set(reg["sections"][kd_key]["upstream"])


def test_resolve_prefers_fetch_cache(tmp_path: Path):
    workflow_scripts = Path(__file__).resolve().parents[2] / "scripts"
    if str(workflow_scripts) not in sys.path:
        sys.path.insert(0, str(workflow_scripts))
    from fetch_template import cache_path  # noqa: E402
    from subagent_config import detect_platform  # noqa: E402

    cached = cache_path(tmp_path, detect_platform(), "tech-plan", "tpt_section_registry_url")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(
        json.dumps(
            {
                "version": "1",
                "section_order": ["NS"],
                "document_preamble": "preamble\n",
                "sections": {
                    "NS": {
                        "heading": "North Star",
                        "aliases": [],
                        "upstream": [],
                        "relations": {},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    from section_registry_schema import resolve_section_registry_path  # noqa: E402

    assert resolve_section_registry_path(tmp_path) == cached


def test_validate_rejects_missing_heading():
    payload = _load_fixture_registry()
    payload["sections"]["NG"]["heading"] = ""
    errors = validate_section_registry(payload)
    assert any("sections.NG.heading" in err for err in errors)


def test_section_desc_preserved():
    reg = _load_fixture_registry()
    assert reg["sections"]["NS"]["desc"].startswith("One clear before")
    assert "desc" in reg["sections"]["T"]
