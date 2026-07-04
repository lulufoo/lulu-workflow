#!/usr/bin/env python3
"""Tests for inductive grounding receipt control."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_GROUNDING_CTL = _INDUCTIVE_DIR / "inductive_grounding_control.py"
_GATE_CTL = _INDUCTIVE_DIR / "inductive_gate_control.py"

sys.path.insert(0, str(_INDUCTIVE_DIR))
from inductive_grounding_schema import (  # noqa: E402
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


def _seed_session(out_dir: Path, *, master_conv: str = "parent-conv") -> None:
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
    _seed_session(tmp_path, master_conv="parent-conv")
    payload = json.dumps([_receipt("I"), _receipt("ST")])
    code, result = _run(
        tmp_path,
        "--conversation-id",
        "parent-conv",
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
        "subagent-conv",
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        json.dumps([_receipt("I")]),
    )
    assert code == 1
    assert "MASTER_CONVERSATION_REQUIRED" in result.get("error", "")


def test_record_grounding_allows_subagent_conversation(tmp_path: Path):
    _seed_session(tmp_path, master_conv="parent-conv")
    payload = json.dumps([_receipt("I"), _receipt("ST")])
    code, result = _run(
        tmp_path,
        "--conversation-id",
        "subagent-conv",
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        payload,
    )
    assert code == 0, result
    assert result.get("count") == 2


def test_check_grounding_passes_when_all_covered(tmp_path: Path):
    _seed_session(tmp_path, master_conv="parent-conv")
    payload = json.dumps([_receipt("I"), _receipt("ST")])
    code, _ = _run(
        tmp_path,
        "--conversation-id",
        "subagent-conv",
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
    _seed_session(tmp_path, master_conv="parent-conv")
    payload = json.dumps([_receipt("I")])
    _run(
        tmp_path,
        "--conversation-id",
        "subagent-conv",
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
    assert "conversation-id" in payload.get("error", "").lower()


def test_schema_max_facts_constant():
    assert MAX_FACTS == 8
