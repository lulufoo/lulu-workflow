#!/usr/bin/env python3
"""Tests for inductive grounding receipt control."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_GROUNDING_CTL = _INDUCTIVE_DIR / "inductive_g3_grounding_control.py"
_GATE_CTL = _INDUCTIVE_DIR / "inductive_gate_control.py"

# Cursor-style UUIDs for SUBAGENT_REQUIRED tests (init-session validates UUID on Cursor).
_PARENT_CONV = "11111111-1111-4111-8111-111111111111"
_SUBAGENT_CONV = "22222222-2222-4222-8222-222222222222"

sys.path.insert(0, str(_INDUCTIVE_DIR))
from g3_grounding_notes_schema import (  # noqa: E402
    MAX_FACT_CHARS,
    MAX_FACTS,
    append_receipts,
    check_sweep_coverage,
    init_ledger,
    validate_receipt,
)


def _run(out_dir: Path, *args: str) -> tuple[int, dict]:
    res = subprocess.run(
        [sys.executable, str(_GROUNDING_CTL), "--out-dir", str(out_dir), *args],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(res.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "raw": res.stdout, "stderr": res.stderr}
    return res.returncode, payload


def _seed_session(out_dir: Path, *, master_conv: str = _PARENT_CONV) -> None:
    res = subprocess.run(
        [
            sys.executable,
            str(_GATE_CTL),
            "--out-dir",
            str(out_dir),
            "init-session",
            "--sections",
            "I,ST",
            "--mandatory",
            "",
            "--cycle-id",
            "c1",
            "--conversation-id",
            master_conv,
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def _receipt(section: str, sweep: int = 1, *, frontier_kw: int = 0) -> dict:
    return {
        "sweep": sweep,
        "mode": "shallow",
        "section": section,
        "frontier_kw": frontier_kw,
        "code_refs": ["main.js::init (L1-10)"],
        "facts": [f"{section} topology present"],
        "produced_by": "subagent",
    }


def test_validate_receipt_rejects_oversized_facts():
    facts = ["x" * (MAX_FACT_CHARS + 1)]
    errors = validate_receipt(
        {
            "id": "GN-001",
            "sweep": 1,
            "mode": "shallow",
            "section": "I",
            "frontier_kw": 0,
            "code_refs": [],
            "facts": facts,
            "produced_by": "subagent",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert errors


def test_validate_receipt_requires_facts_or_clarification():
    errors = validate_receipt(
        {
            "id": "GN-001",
            "sweep": 1,
            "mode": "shallow",
            "section": "I",
            "frontier_kw": 0,
            "code_refs": [],
            "facts": [],
            "produced_by": "subagent",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert errors

    ok = validate_receipt(
        {
            "id": "GN-002",
            "sweep": 1,
            "mode": "shallow",
            "section": "I",
            "frontier_kw": 0,
            "code_refs": [],
            "facts": [],
            "need_clarification": "Which router entrypoint?",
            "produced_by": "subagent",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert ok == []


def test_append_receipts_assigns_ids():
    ledger = init_ledger()
    updated = append_receipts(ledger, [_receipt("I"), _receipt("ST")])
    ids = [r["id"] for r in updated["receipts"]]
    assert ids == ["GN-001", "GN-002"]


def test_append_receipts_rejects_duplicate_section_sweep():
    ledger = append_receipts(init_ledger(), [_receipt("I")])
    try:
        append_receipts(ledger, [_receipt("I")])
    except ValueError as exc:
        assert "duplicate grounding receipt" in str(exc)
    else:
        raise AssertionError("expected duplicate receipt rejection")


def test_check_sweep_coverage_detects_missing():
    unsettled = [
        {"section": "I", "status": "untouched", "frontier_kw": 0},
        {"section": "ST", "status": "untouched", "frontier_kw": 0},
    ]
    result = check_sweep_coverage(init_ledger(), 1, unsettled)
    assert result["ok"] is False
    assert "I" in result["missing"]
    assert "ST" in result["missing"]


def test_check_sweep_coverage_rejects_frontier_kw_mismatch():
    ledger = append_receipts(
        init_ledger(),
        [_receipt("I", frontier_kw=2)],
    )
    unsettled = [{"section": "I", "status": "active", "frontier_kw": 0}]
    result = check_sweep_coverage(ledger, 1, unsettled)
    assert result["ok"] is False
    assert any("frontier_kw" in err for err in result["errors"])


def test_record_grounding_blocks_parent_conversation(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LULU_PLATFORM", raising=False)
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    payload = json.dumps([_receipt("I"), _receipt("ST")])
    code, result = _run(
        tmp_path,
        "--conversation-id",
        _PARENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        payload,
    )
    assert code == 1
    assert "SUBAGENT_REQUIRED" in result.get("error", "")


def test_record_grounding_requires_master_conversation(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LULU_PLATFORM", raising=False)
    gate_path = tmp_path / "inductive-gate-state.json"
    gate_path.write_text(
        json.dumps(
            {
                "version": "1",
                "cycle_id": "c1",
                "stage": "lulu-design",
                "active_gate": "G3",
                "gates": {
                    "G1": {"status": "closed", "closed_at": None, "payload": None},
                    "G2": {"status": "closed", "closed_at": None, "payload": None},
                    "G3": {"status": "active", "closed_at": None, "payload": None},
                    "G4": {"status": "pending", "closed_at": None, "payload": None},
                },
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    ptr = {
        "version": "1",
        "cycle_id": "c1",
        "active_section": None,
        "coverage_order": ["I"],
        "mandatory": [],
        "sections": {"I": {"status": "untouched", "frontier_kw": 0}},
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    (tmp_path / "inductive-section-pointer.json").write_text(
        json.dumps(ptr), encoding="utf-8"
    )

    code, result = _run(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        json.dumps([_receipt("I")]),
    )
    assert code == 1
    assert "MASTER_CONVERSATION_REQUIRED" in result.get("error", "")


def test_record_grounding_allows_subagent_conversation(tmp_path: Path):
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    payload = json.dumps([_receipt("I"), _receipt("ST")])
    code, result = _run(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        payload,
    )
    assert code == 0, result
    assert result.get("count") == 2


def test_check_grounding_passes_when_all_covered(tmp_path: Path):
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    payload = json.dumps([_receipt("I"), _receipt("ST")])
    code, _ = _run(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        payload,
    )
    assert code == 0

    code, result = _run(tmp_path, "check-grounding", "--sweep", "1")
    assert code == 0, result
    assert result.get("unsettled_count") == 2


def test_check_grounding_fails_when_section_missing(tmp_path: Path):
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    payload = json.dumps([_receipt("I")])
    _run(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        payload,
    )

    code, result = _run(tmp_path, "check-grounding", "--sweep", "1")
    assert code == 1
    assert "ST" in result.get("error", "")


def test_unsettled_sections_lists_non_done(tmp_path: Path):
    _seed_session(tmp_path)
    code, result = _run(tmp_path, "unsettled-sections")
    assert code == 0
    sections = {u["section"] for u in result.get("unsettled", [])}
    assert sections == {"I", "ST"}


def test_init_session_requires_conversation_id_on_cursor(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LULU_PLATFORM", raising=False)
    res = subprocess.run(
        [
            sys.executable,
            str(_GATE_CTL),
            "--out-dir",
            str(tmp_path),
            "init-session",
            "--sections",
            "I",
            "--mandatory",
            "",
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(res.stdout)
    assert res.returncode == 1
    assert "platform session identity" in payload.get("error", "").lower()


def test_init_session_rejects_non_uuid_master_on_cursor(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LULU_PLATFORM", raising=False)
    res = subprocess.run(
        [
            sys.executable,
            str(_GATE_CTL),
            "--out-dir",
            str(tmp_path),
            "init-session",
            "--sections",
            "I",
            "--mandatory",
            "",
            "--conversation-id",
            "feature-20260703084622-3b3a7fdd-lulu-design",
        ],
        capture_output=True,
        text=True,
    )
    payload = json.loads(res.stdout)
    assert res.returncode == 1
    assert "invalid platform session identity" in payload.get("error", "").lower()


def test_schema_max_facts_constant():
    assert MAX_FACTS == 8


def _deep_receipt(section: str, ep_id: str, sweep: int = 1, *, frontier_kw: int = 1) -> dict:
    return {
        "sweep": sweep,
        "mode": "deep",
        "section": section,
        "ep_id": ep_id,
        "frontier_kw": frontier_kw,
        "code_refs": ["main.js::init (L12-18)"],
        "facts": [f"{section} {ep_id} concrete signature confirmed"],
        "produced_by": "subagent",
    }


def test_record_grounding_deep_mode_requires_ep_id(tmp_path: Path):
    _seed_session(tmp_path)
    receipt = _deep_receipt("I", "EP-001")
    del receipt["ep_id"]
    code, result = _run(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        json.dumps(receipt),
    )
    assert code == 1
    assert "ep_id" in result.get("error", "")


def test_record_grounding_deep_mode_succeeds_with_ep_id(tmp_path: Path):
    _seed_session(tmp_path)
    code, result = _run(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        json.dumps(_deep_receipt("I", "EP-001")),
    )
    assert code == 0, result
    assert result.get("count") == 1


def test_record_grounding_deep_mode_requires_deep_runner_dispatch(tmp_path: Path):
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    code, result = _run(
        tmp_path,
        "--conversation-id",
        _PARENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        json.dumps(_deep_receipt("I", "EP-001")),
    )
    assert code == 1
    assert "SUBAGENT_REQUIRED" in result.get("error", "")
    assert "g3-deep-grounding-runner" in result.get("error", "")


def test_record_grounding_rejects_mixed_modes_in_one_call(tmp_path: Path):
    _seed_session(tmp_path)
    payload = json.dumps([_receipt("I"), _deep_receipt("ST", "EP-002")])
    code, result = _run(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        payload,
    )
    assert code == 1
    assert "single mode" in result.get("error", "")


def test_deep_receipts_same_section_distinct_ep_ids_do_not_collide(tmp_path: Path):
    _seed_session(tmp_path)
    for ep_id in ("EP-001", "EP-002"):
        code, result = _run(
            tmp_path,
            "--conversation-id",
            _SUBAGENT_CONV,
            "record-grounding",
            "--sweep",
            "1",
            "--json",
            json.dumps(_deep_receipt("I", ep_id)),
        )
        assert code == 0, result

    code, result = _run(tmp_path, "list-grounding", "--sweep", "1", "--mode", "deep")
    assert code == 0, result
    assert result.get("count") == 2


def test_list_grounding_filters_by_ep_id(tmp_path: Path):
    _seed_session(tmp_path)
    for ep_id in ("EP-001", "EP-002"):
        _run(
            tmp_path,
            "--conversation-id",
            _SUBAGENT_CONV,
            "record-grounding",
            "--sweep",
            "1",
            "--json",
            json.dumps(_deep_receipt("I", ep_id)),
        )

    code, result = _run(
        tmp_path, "list-grounding", "--sweep", "1", "--mode", "deep", "--ep-id", "EP-002"
    )
    assert code == 0, result
    assert result.get("count") == 1
    assert result["receipts"][0]["ep_id"] == "EP-002"
