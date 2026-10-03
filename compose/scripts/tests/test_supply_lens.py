#!/usr/bin/env python3
"""Tests for the registry ``supply`` field: G3 asking and deduction filling."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parent.parent
_INDUCTIVE_DIR = _SCRIPTS / "inductive"
sys.path.insert(0, str(_INDUCTIVE_DIR / "open-point"))
sys.path.insert(0, str(_INDUCTIVE_DIR))
for _name in ("gate", "topic", "open-point"):
    sys.path.insert(0, str(_INDUCTIVE_DIR / "schema" / _name))
sys.path.insert(0, str(_SCRIPTS / "deductive" / "derive"))
sys.path.insert(0, str(_SCRIPTS / "templates"))
sys.path.insert(0, str(_SCRIPTS / "_kernel"))

from derive_shell import (  # noqa: E402
    derive_triggers,
    edge_hole_triggers,
    normalize_dependency_graph,
    supplied_lenses,
)
from lens_frontier_schema import load_lens_frontier  # noqa: E402
from open_point_store import (  # noqa: E402
    add_opens,
    check_close,
    ensure_frontier,
    lens_snapshot,
    payable_lenses,
    pending_lenses,
)
from section_registry_schema import dependency_graph_subset, lens_key_sequence  # noqa: E402

_PLAN_REGISTRY = (
    Path(__file__).resolve().parents[3] / "lulu-plan" / "templates" / "section-registry.json"
)
_THREE_SUPPLY_REGISTRY = {
    "version": "1",
    "document_preamble": "test",
    "section_order": ["A", "D", "N"],
    "sections": {
        "A": {"heading": "Ask", "intent": "asked", "supply": "ask"},
        "D": {
            "heading": "Derive",
            "intent": "derived",
            "supply": "derive",
            "upstream": ["A"],
            "relations": {"A": "instantiate"},
        },
        "N": {"heading": "None", "intent": "never", "supply": "none"},
    },
}
_KW = (
    "## A\n\n| KW | Attribute |\n|----|-----------|\n"
    "| KW0 | unnamed |\n| KW1 | readable |\n| KW2 | traceable |\n| KW3 | clear |\n"
)


@pytest.fixture
def three_supply_registry(monkeypatch: pytest.MonkeyPatch):
    def _text(role: str, _slice_dir: Path, _project_root: object = None) -> str:
        if role == "section-registry":
            return json.dumps(_THREE_SUPPLY_REGISTRY)
        if role == "section-kw-criteria":
            return _KW
        raise ValueError(f"{role} missing from SKILL")

    monkeypatch.setattr("open_point_store._skill_template_text", _text)


def _plan_registry() -> dict:
    from section_registry_schema import registry_from_data  # noqa: WPS433

    return registry_from_data(json.loads(_PLAN_REGISTRY.read_text(encoding="utf-8")))


def _plan_supply(registry: dict) -> dict[str, str]:
    return {
        key: registry["sections"][key]["supply"] for key in lens_key_sequence(registry)
    }


def test_pending_lenses_lists_only_ask(tmp_path: Path, three_supply_registry):
    ensure_frontier(tmp_path)
    assert pending_lenses(tmp_path) == ["A"]


def test_payable_lenses_lists_only_ask(tmp_path: Path, three_supply_registry):
    ensure_frontier(tmp_path)
    snapshot = lens_snapshot(tmp_path)
    frontier = load_lens_frontier(tmp_path / "lens-frontier.json")
    assert payable_lenses(snapshot, frontier) == ["A"]


def test_cleared_needs_only_ask_lens_detected(tmp_path: Path, three_supply_registry):
    ensure_frontier(tmp_path)
    detect = {"verdicts": [{"lens": "A", "gap_kw": None, "candidates": []}]}
    add_opens(tmp_path, opens=[], detect=detect)
    assert check_close(tmp_path, mode="cleared")["ok"] is True


def test_detect_rejects_verdict_for_unasked_lens(tmp_path: Path, three_supply_registry):
    ensure_frontier(tmp_path)
    detect = {
        "verdicts": [
            {"lens": lens, "gap_kw": None, "candidates": []} for lens in ("A", "D")
        ]
    }
    with pytest.raises(ValueError, match="unknown lenses"):
        add_opens(tmp_path, opens=[], detect=detect)


def test_plan_registry_marks_sk_and_t_derive():
    supply = _plan_supply(_plan_registry())
    assert supply["SK"] == "derive"
    assert supply["T"] == "derive"
    assert {k for k, v in supply.items() if v == "ask"} == {
        "CTX", "GO", "SC", "AR", "I", "VF",
    }


def test_supplied_lenses_is_group_a_and_direct_dependents():
    order = ["A", "D", "N"]
    supply = {"A": "ask", "D": "derive", "N": "none"}
    graph = normalize_dependency_graph(
        {
            "sections": {
                "A": {"upstream": [], "relations": {}},
                "D": {"upstream": ["A"], "relations": {"A": "instantiate"}},
                "N": {"upstream": ["D"], "relations": {"D": "operationalize"}},
            }
        }
    )
    assert supplied_lenses(order, supply, graph) == ["D"]


def test_plan_participants_are_sk_t_vf():
    registry = _plan_registry()
    graph = normalize_dependency_graph(dependency_graph_subset(registry))
    assert supplied_lenses(
        lens_key_sequence(registry), _plan_supply(registry), graph
    ) == ["SK", "T", "VF"]


def test_plan_deduction_fills_derive_lenses_with_zero_facts():
    registry = _plan_registry()
    graph = normalize_dependency_graph(dependency_graph_subset(registry))
    facts = [
        {"id": "F-1", "text": "arch", "lens": "AR"},
        {"id": "F-2", "text": "intent", "lens": "I"},
    ]
    triggers = derive_triggers(
        lens_key_sequence(registry), _plan_supply(registry), facts, graph
    )
    assert "SK" in triggers
    assert "T" in triggers


def test_plan_vf_edge_holes_come_from_t_facts():
    registry = _plan_registry()
    graph = normalize_dependency_graph(dependency_graph_subset(registry))
    assert graph["sections"]["VF"]["relations"]["T"] == "instantiate"
    facts = [
        {"id": "F-1", "text": "task one", "lens": "T"},
        {"id": "F-2", "text": "kw verification", "lens": "VF"},
    ]
    holes = edge_hole_triggers(
        lens_key_sequence(registry), _plan_supply(registry), facts, graph
    )
    assert holes["VF"] == ["F-1"]


def test_plan_vf_edge_hole_closes_when_vf_cites_t_fact():
    registry = _plan_registry()
    graph = normalize_dependency_graph(dependency_graph_subset(registry))
    facts = [
        {"id": "F-1", "text": "task one", "lens": "T"},
        {
            "id": "F-2",
            "text": "task-level verification",
            "lens": "VF",
            "origin": {"type": "derived", "ref": ["F-1"]},
        },
    ]
    holes = edge_hole_triggers(
        lens_key_sequence(registry), _plan_supply(registry), facts, graph
    )
    assert "VF" not in holes
