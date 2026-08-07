#!/usr/bin/env python3
"""Tests for inductive G2 topology report control."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_G2_CTL = _INDUCTIVE_DIR / "inductive_g2_control.py"
_GATE_CTL = _INDUCTIVE_DIR / "inductive_gate_control.py"

_PARENT_CONV = "11111111-1111-4111-8111-111111111111"
_SUBAGENT_CONV = "22222222-2222-4222-8222-222222222222"

sys.path.insert(0, str(_INDUCTIVE_DIR))
from g2_topology_report_schema import (  # noqa: E402
    MAX_G2_FACT_CHARS,
    validate_report,
)



def _g2_close_payload() -> str:
    """archive-10.0: Topic Loop exit = done + D1/D2 met + human confirm."""
    return (
        '{"topic_loop_done": true, "design_goal_met": true, '
        '"human_exit_confirmed": true}'
    )

def _run_g2(out_dir: Path, *args: str) -> tuple[int, dict]:
    res = subprocess.run(
        [sys.executable, str(_G2_CTL), "--out-dir", str(out_dir), *args],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(res.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "raw": res.stdout, "stderr": res.stderr}
    return res.returncode, payload


def _run_gate(out_dir: Path, *args: str) -> tuple[int, dict]:
    res = subprocess.run(
        [sys.executable, str(_GATE_CTL), "--out-dir", str(out_dir), *args],
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


def _ok_report(**overrides) -> dict:
    base = {
        "verdict": "ok",
        "facts": ["Spine modules exist at expected topology level"],
        "divergences": [],
        "checklist": [],
        "produced_by": "subagent",
    }
    base.update(overrides)
    return base


def _g1_payload() -> str:
    return json.dumps(
        {
            "architecture_view": {
                "as_is": "a",
                "to_be": "b",
                "scope": {"in": ["x"], "out": []},
                "affected_files": [],
                "spine": "s",
                "traces_to": ["upstream"],
            },
            "shape_constraints": [],
            "user_confirmed": True,
        }
    )


def test_validate_report_rejects_line_detail_in_facts():
    errors = validate_report(
        {
            "version": "1",
            "verdict": "ok",
            "facts": ["init in main.js (L12-34)"],
            "divergences": [],
            "checklist": [],
            "produced_by": "subagent",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert errors


def test_validate_report_requires_divergences_when_shape_breaking():
    errors = validate_report(
        {
            "version": "1",
            "verdict": "shape_breaking",
            "facts": [],
            "divergences": [],
            "checklist": [],
            "produced_by": "subagent",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert errors


def test_record_g2_report_blocks_parent_conversation(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("LULU_PLATFORM", raising=False)
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    code, result = _run_g2(
        tmp_path,
        "--conversation-id",
        _PARENT_CONV,
        "record-g2-report",
        "--json",
        json.dumps(_ok_report()),
    )
    assert code == 1
    assert "SUBAGENT_REQUIRED" in result.get("error", "")


def test_record_g2_report_allows_subagent(tmp_path: Path):
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    code, result = _run_g2(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-g2-report",
        "--json",
        json.dumps(_ok_report()),
    )
    assert code == 0, result
    assert result.get("verdict") == "ok"


def test_check_g2_report_passes_on_ok_verdict(tmp_path: Path):
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    _run_g2(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-g2-report",
        "--json",
        json.dumps(_ok_report()),
    )
    code, result = _run_g2(tmp_path, "check-g2-report")
    assert code == 0, result
    assert result.get("verdict") == "ok"


def test_check_g2_report_fails_on_shape_breaking(tmp_path: Path):
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    breaking = _ok_report(
        verdict="shape_breaking",
        facts=[],
        divergences=[
            {
                "shape_claim": "Monolith entry",
                "finding": "Observed microservice split contradicts spine",
                "code_refs": ["svc/a/main.go"],
            }
        ],
    )
    _run_g2(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-g2-report",
        "--json",
        json.dumps(breaking),
    )
    code, result = _run_g2(tmp_path, "check-g2-report")
    assert code == 1
    assert "shape_breaking" in result.get("error", "")


def test_list_g2_report_returns_summary(tmp_path: Path):
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    _run_g2(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-g2-report",
        "--json",
        json.dumps(_ok_report()),
    )
    code, result = _run_g2(tmp_path, "list-g2-report")
    assert code == 0, result
    assert result.get("verdict") == "ok"
    assert len(result.get("facts", [])) == 1


def test_gate_close_g2_requires_design_goal_and_human_exit(tmp_path: Path):
    """archive-10.0: G2 close needs topic_loop_done + design_goal_met + human_exit."""
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    code, _ = _run_gate(tmp_path, "gate-close", "--gate", "G1", "--payload", _g1_payload())
    assert code == 0

    code, _ = _run_gate(
        tmp_path,
        "gate-close",
        "--gate",
        "G2",
        "--payload",
        '{"topic_loop_done": true}',
    )
    assert code != 0  # missing design_goal_met / human_exit_confirmed

    # Draft-as-topic-tree must NOT be required
    assert not (tmp_path / "_narrative-arc.draft.json").exists()

    code, result = _run_gate(
        tmp_path, "gate-close", "--gate", "G2", "--payload", _g2_close_payload()
    )
    assert code == 0, result
    assert result.get("closed") == "G2" or result.get("active_gate") == "G3"


def test_gate_close_g2_succeeds_with_ok_report(tmp_path: Path):
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    _run_gate(tmp_path, "gate-close", "--gate", "G1", "--payload", _g1_payload())
    _run_g2(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-g2-report",
        "--json",
        json.dumps(_ok_report()),
    )

    code, result = _run_gate(
        tmp_path, "gate-close", "--gate", "G2", "--payload", _g2_close_payload()
    )
    assert code == 0, result
    assert result.get("closed") == "G2"



def test_delete_g2_report_removes_file(tmp_path: Path):
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    _run_g2(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-g2-report",
        "--json",
        json.dumps(_ok_report()),
    )
    report_path = tmp_path / "g2-topology-report.json"
    assert report_path.exists()

    code, result = _run_g2(tmp_path, "delete-g2-report")
    assert code == 0, result
    assert result.get("deleted") is True
    assert not report_path.exists()


def test_gate_reopen_g1_deletes_g2_report(tmp_path: Path):
    _seed_session(tmp_path, master_conv=_PARENT_CONV)
    _run_gate(tmp_path, "gate-close", "--gate", "G1", "--payload", _g1_payload())
    _run_g2(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-g2-report",
        "--json",
        json.dumps(_ok_report()),
    )
    report_path = tmp_path / "g2-topology-report.json"
    assert report_path.exists()

    code, result = _run_gate(tmp_path, "gate-reopen", "--gate", "G1")
    assert code == 0, result
    assert result.get("deleted_g2_report") is True
    assert not report_path.exists()


def test_schema_max_fact_chars_constant():
    assert MAX_G2_FACT_CHARS == 120
