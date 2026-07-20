"""Tests for placement_plan_gates.py (archive-3.0 D2)."""

from __future__ import annotations

import sys
from pathlib import Path

_SECTION = Path(__file__).resolve().parent.parent / "section"
sys.path.insert(0, str(_SECTION))

from placement_plan_gates import (  # noqa: E402
    check_l1_placement,
    check_l3_placement,
    check_l4_placement,
    run_placement_plan_gates,
)


def _themes():
    return {
        "version": "1",
        "lens_themes": [
            {
                "form_lens_id": "FL-0",
                "lens_key": "AR",
                "theme": "Arch",
                "desc": "d",
            },
            {
                "form_lens_id": "FL-1",
                "lens_key": "GO",
                "theme": "Goal",
                "desc": "d",
            },
        ],
    }


def _framework():
    return {
        "version": "1",
        "chapters": [
            {
                "id": "ch-1",
                "display_title": "One",
                "anchor_form_lens_ids": ["FL-0", "FL-1"],
                "sections": [
                    {"form_lens_id": "FL-0", "heading": "Arch"},
                    {"form_lens_id": "FL-1", "heading": "Goal"},
                ],
            }
        ],
    }


def _placement(facts):
    return {"version": "1", "$schema_id": "chapter-placement", "chapters": [
        {"id": "ch-1", "facts": facts},
    ]}


def test_l1_placement_ok():
    facts = [
        {"id": "F-1", "text": "a", "lens_tags": ["AR"]},
        {"id": "F-2", "text": "b", "lens_tags": ["GO"]},
    ]
    placement = _placement(
        [
            {"fid": "F-1", "form_lens_id": "FL-0", "placement": "mechanical"},
            {"fid": "F-2", "form_lens_id": "FL-1", "placement": "mechanical"},
        ]
    )
    assert check_l1_placement(facts, placement) == []


def test_l1_placement_unassigned():
    facts = [
        {"id": "F-1", "text": "a", "lens_tags": ["AR"]},
        {"id": "F-2", "text": "b", "lens_tags": ["GO"]},
    ]
    placement = _placement(
        [{"fid": "F-1", "form_lens_id": "FL-0", "placement": "mechanical"}]
    )
    errors = check_l1_placement(facts, placement)
    assert any("F-2" in e and "unassigned" in e for e in errors)


def test_l3_rejects_lens_key_not_in_tags():
    facts = [{"id": "F-1", "text": "a", "lens_tags": ["GO"]}]
    placement = _placement(
        [{"fid": "F-1", "form_lens_id": "FL-0", "placement": "mechanical"}]
    )
    errors = check_l3_placement(facts, placement, _themes(), _framework())
    assert any("lens_key" in e and "F-1" in e for e in errors)


def test_l3_rejects_fl_outside_chapter():
    facts = [{"id": "F-1", "text": "a", "lens_tags": ["AR"]}]
    framework = {
        "version": "1",
        "chapters": [
            {
                "id": "ch-1",
                "display_title": "One",
                "anchor_form_lens_ids": ["FL-1"],
                "sections": [{"form_lens_id": "FL-1", "heading": "Goal"}],
            }
        ],
    }
    placement = _placement(
        [{"fid": "F-1", "form_lens_id": "FL-0", "placement": "mechanical"}]
    )
    errors = check_l3_placement(facts, placement, _themes(), framework)
    assert any("not in chapter" in e for e in errors)


def test_l4_empty_chapter():
    placement = {"version": "1", "chapters": [{"id": "ch-1", "facts": []}]}
    assert any("zero facts" in e for e in check_l4_placement(placement))


def test_run_placement_plan_gates_happy():
    facts = [
        {"id": "F-1", "text": "a", "lens_tags": ["AR"]},
        {"id": "F-2", "text": "b", "lens_tags": ["GO"]},
    ]
    placement = _placement(
        [
            {"fid": "F-1", "form_lens_id": "FL-0", "placement": "mechanical"},
            {"fid": "F-2", "form_lens_id": "FL-1", "placement": "mechanical"},
        ]
    )
    result = run_placement_plan_gates(
        facts,
        placement,
        _themes(),
        _framework(),
        presence_map={"AR": "required", "GO": "optional"},
        section_order=["AR", "GO"],
    )
    assert result["errors"] == []
