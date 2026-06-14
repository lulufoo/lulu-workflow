#!/usr/bin/env python3
"""Tests for probe_report_schema.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from probe_report_schema import (  # noqa: E402
    find_item,
    load_probe_report,
    open_items,
    save_probe_report,
    update_probe_item_decision,
    validate_probe_report,
)
from section_registry_schema import load_section_registry, section_heading  # noqa: E402
from test_registry_fixtures import first_section_key, fourth_section_key  # noqa: E402

_FIXTURE_REGISTRY = Path(__file__).resolve().parent / "test_fixtures" / "section-registry.json"

_KW_CRITERIA = {
    "kw0": "决策未被命名",
    "kw1": "能说出做了什么决策",
    "kw2": "能说出为什么这样判断",
    "kw3": "能说出哪些替代方案被否决",
    "kw4": "能说出这个判断在什么条件下会失效",
}


def _sample_probe(*, probe_seq: int = 1) -> dict:
    section_key = first_section_key()
    heading = section_heading(section_key)
    return {
        "version": "3",
        "kind": "probe",
        "round": 1,
        "revision": 1,
        "cycle_id": "test-cycle",
        "section_key": section_key,
        "section": heading,
        "probe_seq": probe_seq,
        "anchor_failures": [],
        "anchor_candidates": [],
        "items": [
            {
                "id": f"{section_key}-1",
                "gap_kind": "kw",
                "scope": "subsection",
                "section_key": section_key,
                "section": heading,
                "target_kw": 2,
                "intent_gap": "缺少 Why",
                "kw_criteria": _KW_CRITERIA,
                "sub_section_summary": "goal",
                "sub_section_text": "Build faster.",
                "skip_key": f"{section_key}:goal",
                "status": "open",
                "decision": "—",
            }
        ],
    }


def test_validate_accepts_sample():
    assert validate_probe_report(_sample_probe()) == []


def test_open_items_and_find():
    section_key = first_section_key()
    report = _sample_probe()
    assert len(open_items(report)) == 1
    assert find_item(report, f"{section_key}-1") is not None


def test_save_load_roundtrip(tmp_path: Path):
    section_key = first_section_key()
    path = tmp_path / section_key / "probe-001.json"
    save_probe_report(path, _sample_probe())
    loaded = load_probe_report(path)
    assert loaded["probe_seq"] == 1
    assert loaded["items"][0]["gap_kind"] == "kw"


def test_update_decision_preserves_gap_kind():
    section_key = first_section_key()
    item_id = f"{section_key}-1"
    updated = update_probe_item_decision(
        _sample_probe(),
        item_id=item_id,
        decision="accept",
    )
    item = find_item(updated, item_id)
    assert item is not None
    assert item["decision"] == "accept"
    assert item["gap_kind"] == "kw"


def test_rejects_mismatched_section_key():
    payload = _sample_probe()
    payload["items"][0]["section_key"] = fourth_section_key()
    errors = validate_probe_report(payload)
    assert any("does not match report section" in err for err in errors)


def test_accepts_upstream_coverage_item():
    reg = load_section_registry(_FIXTURE_REGISTRY)
    section_key = fourth_section_key()
    heading = section_heading(section_key)
    upstream = reg["sections"][section_key]["upstream"][0]
    payload = _sample_probe()
    payload["section_key"] = section_key
    payload["section"] = heading
    payload["items"] = [
        {
            "id": f"{section_key}-U-{upstream}-1",
            "gap_kind": "upstream_coverage",
            "scope": "section",
            "section_key": section_key,
            "section": heading,
            "upstream_section": upstream,
            "upstream_relation": "operationalize",
            "target_kw": None,
            "intent_gap": f"{section_key} 未 operationalize {upstream}",
            "kw_criteria": None,
            "upstream_criteria": {
                "upstream_intent": "降低运维成本",
                "expected": f"{section_key} 应有对应决策",
                "observed": "无",
            },
            "sub_section_summary": f"{section_key} 相对 {upstream} coverage",
            "sub_section_text": f"（{section_key} 整节）",
            "skip_key": f"{section_key}:upstream:{upstream}",
            "status": "open",
            "decision": "—",
        }
    ]
    assert validate_probe_report(payload) == []


def test_refiner_payload_upstream():
    from probe_report_schema import refiner_payload

    reg = load_section_registry(_FIXTURE_REGISTRY)
    section_key = fourth_section_key()
    heading = section_heading(section_key)
    upstream = reg["sections"][section_key]["upstream"][0]
    item = {
        "id": f"{section_key}-U-{upstream}-1",
        "gap_kind": "upstream_coverage",
        "scope": "section",
        "section": heading,
        "section_key": section_key,
        "sub_section_text": "body",
        "intent_gap": "gap",
        "upstream_section": upstream,
        "upstream_relation": "operationalize",
        "upstream_criteria": {"upstream_intent": "a", "expected": "b", "observed": "c"},
    }
    payload = refiner_payload(item)
    assert payload["gap_kind"] == "upstream_coverage"
    assert payload["upstream_section"] == upstream
    assert payload["target_kw"] is None
