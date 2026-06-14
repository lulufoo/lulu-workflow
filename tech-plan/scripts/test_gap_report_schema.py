#!/usr/bin/env python3
"""Tests for gap_report_schema.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gap_report_schema import (  # noqa: E402
    find_item,
    load_gap_report,
    open_items,
    refiner_payload,
    save_gap_report,
    undecided_items,
    update_item_decision,
    validate_gap_report,
)
from section_registry_schema import section_heading  # noqa: E402
from test_registry_fixtures import fourth_section_key, fifth_section_key, third_section_key  # noqa: E402

_KW_CRITERIA = {
    "kw0": "决策未被命名",
    "kw1": "能说出做了什么决策",
    "kw2": "能说出为什么这样判断",
    "kw3": "能说出哪些替代方案被否决",
    "kw4": "能说出这个判断在什么条件下会失效",
}


def _sample_payload(*, round_n: int = 2) -> dict:
    sk_key = fifth_section_key()
    sk_heading = section_heading(sk_key)
    i_key = third_section_key()
    i_heading = section_heading(i_key)
    kd_key = fourth_section_key()
    return {
        "version": "2",
        "round": round_n,
        "revision": 1,
        "cycle_id": "topic-test",
        "anchor_failures": [],
        "anchor_candidates": [{"scenario": "P0 spike", "target": f"{kd_key} KW4"}],
        "items": [
            {
                "id": f"{sk_key}-1",
                "section_key": sk_key,
                "section": sk_heading,
                "target_kw": 2,
                "intent_gap": "每个阶段缺少 Done 判据",
                "kw_criteria": _KW_CRITERIA,
                "sub_section_summary": "phase plan missing done criteria",
                "sub_section_text": "Only dependency table.",
                "skip_key": f"{sk_key}:phase-plan",
                "status": "open",
                "decision": "—",
            },
            {
                "id": f"{i_key}-0",
                "section_key": i_key,
                "section": i_heading,
                "target_kw": None,
                "intent_gap": "",
                "kw_criteria": None,
                "sub_section_summary": f"{i_heading} complete",
                "sub_section_text": "Obligations listed.",
                "skip_key": f"{i_key}:obligations",
                "status": "no_gap",
                "decision": "—",
            },
        ],
    }


def test_validate_accepts_sample_payload():
    assert validate_gap_report(_sample_payload()) == []


def test_open_items_filters_status():
    sk_key = fifth_section_key()
    report = _sample_payload()
    assert len(open_items(report)) == 1
    assert open_items(report)[0]["id"] == f"{sk_key}-1"


def test_undecided_items_excludes_decided_open():
    sk_key = fifth_section_key()
    report = update_item_decision(_sample_payload(), item_id=f"{sk_key}-1", decision="skip")
    assert len(open_items(report)) == 1
    assert len(undecided_items(report)) == 0


def test_save_and_load_roundtrip(tmp_path: Path):
    sk_key = fifth_section_key()
    path = tmp_path / "gap-report-round-2.json"
    save_gap_report(path, _sample_payload())
    loaded = load_gap_report(path)
    assert loaded["round"] == 2
    assert find_item(loaded, f"{sk_key}-1") is not None


def test_update_item_decision():
    sk_key = fifth_section_key()
    updated = update_item_decision(_sample_payload(), item_id=f"{sk_key}-1", decision="accept")
    assert find_item(updated, f"{sk_key}-1")["decision"] == "accept"


def test_refiner_payload_fields():
    sk_key = fifth_section_key()
    item = find_item(_sample_payload(), f"{sk_key}-1")
    assert item is not None
    payload = refiner_payload(item)
    assert payload["gap_item_id"] == f"{sk_key}-1"
    assert payload["target_kw"] == 2
    assert payload["intent_gap"] == "每个阶段缺少 Done 判据"
    assert payload["kw_criteria"] == _KW_CRITERIA


def test_rejects_open_without_target_kw():
    payload = _sample_payload()
    del payload["items"][0]["target_kw"]
    errors = validate_gap_report(payload)
    assert any("target_kw required" in err for err in errors)


def test_rejects_open_without_kw_criteria():
    payload = _sample_payload()
    payload["items"][0]["kw_criteria"] = None
    errors = validate_gap_report(payload)
    assert any("kw_criteria required" in err for err in errors)


def test_rejects_open_with_incomplete_kw_criteria():
    payload = _sample_payload()
    payload["items"][0]["kw_criteria"] = {"kw1": "only one key"}
    errors = validate_gap_report(payload)
    assert any("kw_criteria.kw0 required" in err for err in errors)


def test_accepts_kw0_pending_item():
    kd_key = fourth_section_key()
    kd_heading = section_heading(kd_key)
    payload = _sample_payload()
    payload["items"].append(
        {
            "id": f"{kd_key}-2",
            "section_key": kd_key,
            "section": kd_heading,
            "target_kw": None,
            "intent_gap": f"请补充这条 {kd_heading} 的内容",
            "kw_criteria": None,
            "sub_section_summary": "empty decision",
            "sub_section_text": "",
            "skip_key": f"{kd_key}:empty",
            "status": "kw0_pending",
            "decision": "—",
        }
    )
    assert validate_gap_report(payload) == []


def test_kw0_pending_items_filter():
    kd_key = fourth_section_key()
    kd_heading = section_heading(kd_key)
    payload = _sample_payload()
    payload["items"].append(
        {
            "id": f"{kd_key}-2",
            "section_key": kd_key,
            "section": kd_heading,
            "target_kw": None,
            "intent_gap": "请补充",
            "kw_criteria": None,
            "sub_section_summary": "empty",
            "sub_section_text": "",
            "skip_key": f"{kd_key}:empty",
            "status": "kw0_pending",
            "decision": "—",
        }
    )
    from gap_report_schema import kw0_pending_items

    assert len(kw0_pending_items(payload)) == 1


def test_rejects_wrong_version():
    payload = _sample_payload()
    payload["version"] = "1"
    errors = validate_gap_report(payload)
    assert any("version" in err for err in errors)
