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
from section_registry_schema import load_section_registry  # noqa: E402
from test_registry_fixtures import fourth_section_key  # noqa: E402

import json


def _registry_path(tmp_path: Path) -> Path:
    source = (
        Path(__file__).resolve().parents[3]
        / "lulu-plan"
        / "templates"
        / "section-registry.json"
    )
    path = tmp_path / "section-registry.json"
    path.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return path


def test_section_upstream_edges_from_registry(tmp_path: Path):
    registry_path = _registry_path(tmp_path)
    reg = load_section_registry(registry_path)
    section_key = fourth_section_key()
    graph = load_dependency_graph(registry_path)
    edges = upstream_edges(section_key, graph)
    keys = {edge["upstream_section"] for edge in edges}
    assert keys == set(reg["sections"][section_key]["upstream"])
    assert edges[0]["upstream_relation"] == "operationalize"


def test_stable_upstream_filters_pointer(tmp_path: Path):
    registry_path = _registry_path(tmp_path)
    reg = load_section_registry(registry_path)
    section_key = fourth_section_key()
    upstream = reg["sections"][section_key]["upstream"]
    graph = load_dependency_graph(registry_path)
    pointer = {
        "sections": {
            key: {"status": "stable" if key in upstream[:2] else "pending"}
            for key in reg["section_order"]
        },
    }
    stable = stable_upstream_edges(section_key, graph, pointer)
    assert {edge["upstream_section"] for edge in stable} == set(upstream[:2])
