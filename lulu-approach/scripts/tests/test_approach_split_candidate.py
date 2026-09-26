#!/usr/bin/env python3
"""Tests for temporary Split candidate topology and C-to-D projection."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
_SCHEMA = _SCRIPTS / "schema"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _candidate():
    path = _SCHEMA / "approach_split_candidate_schema.py"
    if not path.is_file():
        pytest.fail("approach_split_candidate_schema.py must define Split candidates")
    return _load("approach_split_candidate_schema", path)


def _candidate_payload() -> dict:
    return {
        "nodes": [
            {"id": "C1", "title": "host", "summary": "host seam"},
            {"id": "C2", "title": "entry", "summary": "entry seam"},
        ],
        "edges": [{"from": "C2", "to": "C1"}],
        "order": ["C1", "C2"],
        "cut_axis": "domain_seam",
        "rulers": {
            "C1": {
                "id": "C1",
                "job": "define host",
                "boundary": "no entry",
                "deps_summary": "none",
            },
            "C2": {
                "id": "C2",
                "job": "define entry",
                "boundary": "consume host",
                "deps_summary": "depends on C1",
            },
        },
        "mapping": {
            "C1": {"kind": "existing", "node_id": "D2"},
            "C2": {"kind": "new", "node_id": "D3"},
        },
    }


def test_candidate_materializes_temporary_c_ids_to_confirmed_d_ids() -> None:
    candidate = _candidate().build_candidate(**_candidate_payload())

    tree, rulers = _candidate().materialize_candidate(candidate)

    assert [node["id"] for node in tree["nodes"]] == ["D2", "D3"]
    assert tree["edges"] == [{"from": "D3", "to": "D2"}]
    assert tree["order"] == ["D2", "D3"]
    assert rulers["rulers"]["D2"]["id"] == "D2"
    assert rulers["rulers"]["D3"]["id"] == "D3"


def test_structure_signature_ignores_candidate_content_fields() -> None:
    candidate = _candidate().build_candidate(**_candidate_payload())
    tree, _ = _candidate().materialize_candidate(candidate)
    content_changed = {
        **tree,
        "nodes": [
            {"id": "D2", "title": "renamed", "summary": "different wording"},
            {"id": "D3", "title": "different", "summary": "different wording"},
        ],
    }

    assert _candidate().structure_signature(tree) == _candidate().structure_signature(
        content_changed
    )


def test_structure_signature_normalizes_edge_order() -> None:
    first = {
        "nodes": [{"id": "D1"}, {"id": "D2"}, {"id": "D3"}],
        "edges": [{"from": "D2", "to": "D1"}, {"from": "D3", "to": "D1"}],
        "order": ["D1", "D2", "D3"],
    }
    reordered = {**first, "edges": list(reversed(first["edges"]))}

    assert _candidate().structure_signature(first) == _candidate().structure_signature(
        reordered
    )


def test_candidate_round_trip_uses_its_transaction_directory(tmp_path: Path) -> None:
    candidate = _candidate().build_candidate(**_candidate_payload())

    path = _candidate().save_candidate(tmp_path, "mlr-001", candidate)

    assert path == tmp_path / "mainline-reopen" / "mlr-001" / "candidate.json"
    assert _candidate().load_candidate(tmp_path, "mlr-001") == candidate
