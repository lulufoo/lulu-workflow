#!/usr/bin/env python3
"""Tests for section_dependency_schema.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from section_dependency_schema import (  # noqa: E402
    load_dependency_graph,
    stable_upstream_edges,
    upstream_edges,
)
from section_pointer_schema import init_section_pointer, mark_section_stable  # noqa: E402
from section_registry_schema import load_section_registry  # noqa: E402
from test_registry_fixtures import fourth_section_key  # noqa: E402


_FIXTURE_REGISTRY = Path(__file__).resolve().parent / "test_fixtures" / "section-registry.json"


def test_section_upstream_edges_from_registry():
    reg = load_section_registry(_FIXTURE_REGISTRY)
    section_key = fourth_section_key()
    graph = load_dependency_graph(_FIXTURE_REGISTRY)
    edges = upstream_edges(section_key, graph)
    keys = {edge["upstream_section"] for edge in edges}
    assert keys == set(reg["sections"][section_key]["upstream"])
    assert edges[0]["upstream_relation"] == "operationalize"


def test_stable_upstream_filters_pointer():
    reg = load_section_registry(_FIXTURE_REGISTRY)
    section_key = fourth_section_key()
    upstream = reg["sections"][section_key]["upstream"]
    graph = load_dependency_graph(_FIXTURE_REGISTRY)
    pointer = init_section_pointer(round_n=1, revision=1, cycle_id="c1")
    for key in upstream[:2]:
        pointer = mark_section_stable(pointer, key)
    stable = stable_upstream_edges(section_key, graph, pointer)
    assert {edge["upstream_section"] for edge in stable} == set(upstream[:2])
