#!/usr/bin/env python3
"""Tests for section_dependency_schema.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from section_dependency_schema import (  # noqa: E402
    dependency_graph_from_data,
    stable_upstream_edges,
    upstream_edges,
)
from section_registry_schema import registry_from_data  # noqa: E402
from test_registry_fixtures import fourth_section_key  # noqa: E402

import json


def _fixture_registry() -> dict:
    source = (
        Path(__file__).resolve().parents[3]
        / "lulu-plan"
        / "templates"
        / "section-registry.json"
    )
    return registry_from_data(json.loads(source.read_text(encoding="utf-8")))


def test_section_upstream_edges_from_registry():
    reg = _fixture_registry()
    section_key = fourth_section_key()
    graph = dependency_graph_from_data(reg)
    edges = upstream_edges(section_key, graph)
    keys = {edge["upstream_section"] for edge in edges}
    assert keys == set(reg["sections"][section_key]["upstream"])
    assert edges[0]["upstream_relation"] == "operationalize"


def test_stable_upstream_filters_pointer():
    reg = _fixture_registry()
    section_key = fourth_section_key()
    upstream = reg["sections"][section_key]["upstream"]
    graph = dependency_graph_from_data(reg)
    pointer = {
        "sections": {
            key: {"status": "stable" if key in upstream[:2] else "pending"}
            for key in reg["section_order"]
        },
    }
    stable = stable_upstream_edges(section_key, graph, pointer)
    assert {edge["upstream_section"] for edge in stable} == set(upstream[:2])
