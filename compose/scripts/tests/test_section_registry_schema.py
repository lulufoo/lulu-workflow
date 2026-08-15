#!/usr/bin/env python3
"""Tests for section_registry_schema.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bootstrap  # noqa: F401

from section_registry_schema import (  # noqa: E402
    document_preamble,
    initial_fill_results,
    load_section_registry,
    normalize_section,
    normalize_section_registry,
    section_heading,
    section_keys,
    section_order,
    upstream_edges,
    validate_section_registry,
)
from section_dependency_schema import load_dependency_graph  # noqa: E402
from test_template_data import legacy_section_registry_normalized  # noqa: E402


def _load_fixture_registry() -> dict:
    path = (
        Path(__file__).resolve().parents[3]
        / "lulu-plan"
        / "templates"
        / "section-registry.json"
    )
    return normalize_section_registry(json.loads(path.read_text(encoding="utf-8")))


def _load_legacy_fixture_registry() -> dict:
    return legacy_section_registry_normalized()


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


def test_upstream_edges_from_registry(tmp_path: Path):
    reg = _load_fixture_registry()
    kd_key = reg["section_order"][3]
    registry_path = tmp_path / "section-registry.json"
    registry_path.write_text(json.dumps(reg), encoding="utf-8")
    graph = load_dependency_graph(registry_path)
    edges = upstream_edges(kd_key, graph)
    assert {e["upstream_section"] for e in edges} == set(reg["sections"][kd_key]["upstream"])


def test_resolve_uses_direct_skill_template_ref(tmp_path: Path):
    from section_registry_schema import resolve_section_registry_path  # noqa: E402

    expected = (
        Path(__file__).resolve().parents[3]
        / "lulu-plan"
        / "templates"
        / "section-registry.json"
    )
    assert resolve_section_registry_path(tmp_path) == expected


def test_validate_rejects_missing_heading():
    payload = _load_legacy_fixture_registry()
    payload["sections"]["NG"]["heading"] = ""
    errors = validate_section_registry(payload)
    assert any("sections.NG.heading" in err for err in errors)


def test_section_desc_preserved():
    reg = _load_legacy_fixture_registry()
    assert reg["sections"]["NS"]["desc"].startswith("One clear before")
    assert "desc" in reg["sections"]["T"]


def test_intent_copied_to_desc_on_normalize():
    payload = {
        "version": "1",
        "section_order": ["GO"],
        "document_preamble": "preamble\n",
        "sections": {
            "GO": {
                "heading": "Goal",
                "aliases": [],
                "upstream": [],
                "relations": {},
                "intent": "Outcome text.",
                "intent_boundary": "Tasks belong to T.",
            }
        },
    }
    from section_registry_schema import normalize_section_registry  # noqa: E402

    normalized = normalize_section_registry(payload)
    assert normalized["sections"]["GO"]["desc"] == "Outcome text."
    assert normalized["sections"]["GO"]["intent_boundary"] == "Tasks belong to T."


def test_validate_requires_intent_or_desc():
    payload = _load_legacy_fixture_registry()
    key = payload["section_order"][0]
    payload["sections"][key].pop("desc", None)
    errors = validate_section_registry(payload)
    assert any("requires intent or desc" in err for err in errors)


def test_summary_section_key_prefers_go(monkeypatch):
    from section_registry_schema import summary_section_key  # noqa: E402

    monkeypatch.setattr(
        "section_registry_schema.section_order",
        lambda project_root=None: ("CTX", "GO", "SC"),
    )
    assert summary_section_key() == "GO"

    monkeypatch.setattr(
        "section_registry_schema.section_order",
        lambda project_root=None: ("NS", "NG"),
    )
    assert summary_section_key() == "NS"


def test_validate_tech_design_section_registry_intent_only():
    errors = validate_section_registry(TECH_DESIGN_INTENT)
    assert errors == []


def test_validate_rejects_guidance_in_section_registry():
    payload = json.loads(json.dumps(TECH_DESIGN_INTENT))
    payload["sections"]["CTX"]["guidance"] = "Narrative first."
    errors = validate_section_registry(payload)
    assert any("guidance is not supported" in err for err in errors)


def test_validate_rejects_contract_in_section_registry():
    payload = json.loads(json.dumps(TECH_DESIGN_INTENT))
    payload["sections"]["CTX"]["contract"] = {"required": ["x"], "forbidden": []}
    errors = validate_section_registry(payload)
    assert any("contract is not supported" in err for err in errors)


from framework_template_sources import (  # noqa: E402
    tech_design_section_form_registry,
    tech_design_section_registry,
)

TECH_DESIGN_INTENT = tech_design_section_registry()
TECH_DESIGN_FORM = tech_design_section_form_registry()


def test_presence_defaults_to_required_on_normalize():
    payload = {
        "version": "1",
        "section_order": ["GO", "NG"],
        "document_preamble": "preamble\n",
        "sections": {
            "GO": {"heading": "Goal", "intent": "x"},
            "NG": {"heading": "Non-Goals", "intent": "y", "presence": "optional"},
        },
    }
    normalized = normalize_section_registry(payload)
    assert normalized["sections"]["GO"]["presence"] == "required"
    assert normalized["sections"]["NG"]["presence"] == "optional"


def test_presence_null_defaults_to_required():
    payload = {
        "version": "1",
        "section_order": ["GO"],
        "document_preamble": "preamble\n",
        "sections": {"GO": {"heading": "Goal", "intent": "x", "presence": None}},
    }
    assert validate_section_registry(payload) == []
    assert normalize_section_registry(payload)["sections"]["GO"]["presence"] == "required"


def test_validate_rejects_invalid_presence_value():
    payload = {
        "version": "1",
        "section_order": ["GO"],
        "document_preamble": "preamble\n",
        "sections": {"GO": {"heading": "Goal", "intent": "x", "presence": "sometimes"}},
    }
    errors = validate_section_registry(payload)
    assert any("sections.GO.presence must be one of" in err for err in errors)


def test_section_presence_map(monkeypatch):
    import section_registry_schema as schema_mod  # noqa: E402

    fake_registry = normalize_section_registry(
        {
            "version": "1",
            "section_order": ["GO", "NG"],
            "document_preamble": "preamble\n",
            "sections": {
                "GO": {"heading": "Goal", "intent": "x"},
                "NG": {"heading": "Non-Goals", "intent": "y", "presence": "optional"},
            },
        },
    )
    monkeypatch.setattr(schema_mod, "_active_registry", lambda project_root=None: fake_registry)
    assert schema_mod.section_presence_map() == {"GO": "required", "NG": "optional"}


def test_cluster_preserved_on_normalize():
    payload = {
        "version": "1",
        "section_order": ["OBS", "REL"],
        "document_preamble": "preamble\n",
        "sections": {
            "OBS": {
                "heading": "Observability",
                "intent": "x",
                "cluster": "stability-design",
            },
            "REL": {
                "heading": "Release",
                "intent": "y",
                "cluster": "stability-design",
            },
        },
    }
    assert validate_section_registry(payload) == []
    normalized = normalize_section_registry(payload)
    assert normalized["sections"]["OBS"]["cluster"] == "stability-design"
    assert normalized["sections"]["REL"]["cluster"] == "stability-design"


def test_validate_rejects_invalid_cluster_slug():
    payload = {
        "version": "1",
        "section_order": ["GO"],
        "document_preamble": "preamble\n",
        "sections": {
            "GO": {"heading": "Goal", "intent": "x", "cluster": "Stability_Design"},
        },
    }
    errors = validate_section_registry(payload)
    assert any("sections.GO.cluster must match" in err for err in errors)


def test_section_cluster_map(monkeypatch):
    import section_registry_schema as schema_mod  # noqa: E402

    fake_registry = normalize_section_registry(
        {
            "version": "1",
            "section_order": ["GO", "OBS", "REL"],
            "document_preamble": "preamble\n",
            "sections": {
                "GO": {"heading": "Goal", "intent": "g"},
                "OBS": {
                    "heading": "Observability",
                    "intent": "o",
                    "cluster": "stability-design",
                },
                "REL": {
                    "heading": "Release",
                    "intent": "r",
                    "cluster": "stability-design",
                },
            },
        },
    )
    monkeypatch.setattr(schema_mod, "_active_registry", lambda project_root=None: fake_registry)
    assert schema_mod.section_cluster_map() == {
        "OBS": "stability-design",
        "REL": "stability-design",
    }


def test_section_guidance_and_contract_accessors(tmp_path: Path):
    from section_form_registry_schema import (  # noqa: E402
        load_section_form_registry,
        merge_section_form_into_registry,
    )

    intent_path = tmp_path / "section-registry.json"
    form_path = tmp_path / "section-form-registry.json"
    intent_path.write_text(json.dumps(TECH_DESIGN_INTENT), encoding="utf-8")
    form_path.write_text(json.dumps(TECH_DESIGN_FORM), encoding="utf-8")
    intent = load_section_registry(intent_path)
    form = load_section_form_registry(form_path, intent_registry=intent)
    merged = merge_section_form_into_registry(intent, form)
    assert merged["sections"]["CTX"]["presentation"]["guidance"]
    assert merged["sections"]["CTX"]["expression"]["required"]
    assert "reading_axis" in merged["sections"]["CTX"]


def test_registry_without_section_order_uses_sections_keys():
    """archive-5.0: section_order optional; lens set = sections keys."""
    payload = {
        "version": "1",
        "document_preamble": "preamble\n",
        "sections": {
            "GOAL": {
                "heading": "Goal",
                "aliases": [],
                "upstream": [],
                "relations": {},
                "intent": "Success line.",
            },
            "I": {
                "heading": "Invariants",
                "aliases": [],
                "upstream": ["GOAL"],
                "relations": {"GOAL": "operationalize"},
                "intent": "Always-hold checks.",
            },
        },
    }
    assert validate_section_registry(payload) == []
    normalized = normalize_section_registry(payload)
    assert "section_order" not in normalized
    assert set(normalized["sections"]) == {"GOAL", "I"}
