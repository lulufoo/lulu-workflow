#!/usr/bin/env python3
"""Tests for inductive G4 internal-audit report control + gate-close G4."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_G4_CTL = _INDUCTIVE_DIR / "inductive_g4_control.py"
_GATE_CTL = _INDUCTIVE_DIR / "inductive_gate_control.py"
_SCHEMA_DIR = _INDUCTIVE_DIR / "schema"
_SECTION = Path(__file__).resolve().parent.parent / "section"

sys.path.insert(0, str(_INDUCTIVE_DIR))
sys.path.insert(0, str(_SCHEMA_DIR))
sys.path.insert(0, str(_SECTION))

from compose_state_lock import canonical_digest  # noqa: E402
from g4_recompose_report_schema import g4_report_path  # noqa: E402
from open_point_store import add_opens, ensure_frontier, frontier_digest, set_frontier  # noqa: E402

_PARENT_CONV = "11111111-1111-4111-8111-111111111111"
_SUBAGENT_CONV = "22222222-2222-4222-8222-222222222222"


def _g2_close_payload() -> str:
    return (
        '{"topic_loop_done": true, "design_goal_met": true, '
        '"human_exit_confirmed": true, "topic_exit": "cleared"}'
    )


def _run_g4(out_dir: Path, *args: str) -> tuple[int, dict]:
    res = subprocess.run(
        [sys.executable, str(_G4_CTL), "--out-dir", str(out_dir), *args],
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


def _g2_prepare_exit(out_dir: Path) -> None:
    code, payload = _run_gate(
        out_dir,
        "record-topic-landscape",
        "--purpose",
        "pre_close",
        "--gap-remaining",
        "0",
    )
    assert code == 0, payload
    code, payload = _run_gate(
        out_dir,
        "record-g2-topic-exit",
        "--result",
        "cleared",
        "--human-confirmed",
    )
    assert code == 0, payload


def _json_or_empty(path: Path):
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _current_digests(slice_dir: Path) -> tuple[str, str]:
    return (
        canonical_digest(_json_or_empty(slice_dir / "_facts.json")),
        canonical_digest(_json_or_empty(slice_dir / "inductive-opens.json")),
    )


def _ready_cleared(slice_dir: Path) -> None:
    (slice_dir / "section-registry.json").write_text(
        json.dumps(
            {
                "version": "1",
                "document_preamble": "test",
                "section_order": ["I"],
                "sections": {
                    "I": {
                        "heading": "Intent",
                        "intent": "constraints",
                        "presence": "required",
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (slice_dir / "section-kw-criteria.md").write_text(
        "## I\n\n| KW | x |\n|----|---|\n| KW0 | n |\n| KW1 | r |\n| KW3 | b |\n",
        encoding="utf-8",
    )
    ensure_frontier(slice_dir)
    set_frontier(slice_dir, "I", 3)
    (slice_dir / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-seed", "text": "g4 lens source", "lens_tags": ["I"]}]
        )
        + "\n",
        encoding="utf-8",
    )


def _detect_meta(slice_dir: Path, raw_candidates):
    facts = _json_or_empty(slice_dir / "_facts.json")
    lenses = _json_or_empty(slice_dir / "section-registry.json")
    opens = _json_or_empty(slice_dir / "inductive-opens.json")
    facts_d = canonical_digest(facts)
    lens_d = canonical_digest(lenses)
    opens_d = canonical_digest(opens)
    ensure_frontier(slice_dir)
    frontier_d = frontier_digest(slice_dir)
    return {
        "checked_lenses": ["I"],
        "facts_digest": facts_d,
        "lens_digest": lens_d,
        "opens_digest": opens_d,
        "frontier_digest": frontier_d,
        "raw_candidates": list(raw_candidates),
        "expected_facts_digest": facts_d,
        "expected_lens_digest": lens_d,
        "expected_opens_digest": opens_d,
        "expected_frontier_digest": frontier_d,
        "inert_means": ["intent", "scan"],
    }


def _ok_recompose_report(out_dir: Path, **overrides) -> dict:
    facts_digest, opens_digest = _current_digests(out_dir)
    base = {
        "version": 1,
        "facts_digest": facts_digest,
        "opens_digest": opens_digest,
        "findings": [],
        "buildable": True,
        "reversible": True,
        "verifiable": True,
        "evidence": {
            "buildable": "facts compose a buildable set",
            "reversible": "consequential actions have reversal paths",
            "verifiable": "settled claims have observable checks",
        },
        "produced_by": "subagent",
    }
    base.update(overrides)
    return base


def _drive_to_g4(tmp_path: Path) -> None:
    res = subprocess.run(
        [
            sys.executable,
            str(_GATE_CTL),
            "--out-dir",
            str(tmp_path),
            "init-session",
            "--cycle-id",
            "c1",
            "--conversation-id",
            _PARENT_CONV,
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G1")
    assert code == 0, result
    _g2_prepare_exit(tmp_path)
    code, result = _run_gate(
        tmp_path, "gate-close", "--gate", "G2", "--payload", _g2_close_payload()
    )
    assert code == 0, result
    _ready_cleared(tmp_path)
    add_opens(tmp_path, opens=[], detect=_detect_meta(tmp_path, []))
    code, result = _run_gate(
        tmp_path, "gate-close", "--gate", "G3", "--mode", "cleared", "--confirm"
    )
    assert code == 0, result


def _record_ok_recompose_report(tmp_path: Path, **overrides) -> tuple[int, dict]:
    return _run_g4(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-recompose-report",
        "--json",
        json.dumps(_ok_recompose_report(tmp_path, **overrides)),
    )


def test_record_recompose_report_allows_parent_conversation(tmp_path: Path):
    _drive_to_g4(tmp_path)
    code, result = _run_g4(
        tmp_path,
        "--conversation-id",
        _PARENT_CONV,
        "record-recompose-report",
        "--json",
        json.dumps(_ok_recompose_report(tmp_path)),
    )
    assert code == 0, result


def test_record_recompose_report_accepts_runner_return_shape(tmp_path: Path):
    _drive_to_g4(tmp_path)
    facts_digest, opens_digest = _current_digests(tmp_path)
    runner_return = {
        "echoed_digests": {"facts": facts_digest, "opens": opens_digest},
        "findings": [
            {
                "question": "Who owns retry?",
                "evidence": "Two facts disagree",
                "blocking": True,
                "lens": "I",
            }
        ],
        "buildable": False,
        "reversible": True,
        "verifiable": True,
        "evidence": {
            "buildable": "retry owner is split",
            "reversible": "reversal paths look present",
            "verifiable": "settled claims look checkable",
        },
    }
    code, result = _run_g4(
        tmp_path,
        "record-recompose-report",
        "--json",
        json.dumps(runner_return),
    )
    assert code == 0, result
    assert result["findings"][0]["basis"] == "Two facts disagree"


def test_record_recompose_report_allows_subagent(tmp_path: Path):
    _drive_to_g4(tmp_path)
    code, result = _record_ok_recompose_report(tmp_path)
    assert code == 0, result


def test_record_recompose_report_rejects_stale_digest(tmp_path: Path):
    _drive_to_g4(tmp_path)
    stale = _ok_recompose_report(tmp_path, opens_digest="0" * 64)
    code, result = _run_g4(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-recompose-report",
        "--json",
        json.dumps(stale),
    )
    assert code == 1
    assert "stale" in result.get("error", "").lower() or "digest" in result.get("error", "").lower()


def test_check_recompose_report_passes_when_closable(tmp_path: Path):
    _drive_to_g4(tmp_path)
    _record_ok_recompose_report(tmp_path)
    code, result = _run_g4(tmp_path, "check-recompose-report")
    assert code == 0, result
    assert result.get("closable") is True
    assert result.get("findings") == []
    assert "facts_digest" in result
    assert "opens_digest" in result


def test_check_recompose_report_fails_on_findings(tmp_path: Path):
    _drive_to_g4(tmp_path)
    _record_ok_recompose_report(
        tmp_path,
        findings=[
            {
                "question": "Who owns retry?",
                "basis": "Two facts disagree",
                "blocking": True,
                "lens": "I",
            }
        ],
        buildable=False,
    )
    code, result = _run_g4(tmp_path, "check-recompose-report")
    assert code == 1
    assert "finding" in result.get("error", "").lower() or result.get("ok") is False


def test_list_recompose_report_returns_findings_predicates_digests(tmp_path: Path):
    _drive_to_g4(tmp_path)
    facts_digest, opens_digest = _current_digests(tmp_path)
    _record_ok_recompose_report(tmp_path)
    code, result = _run_g4(tmp_path, "list-recompose-report")
    assert code == 0, result
    assert result.get("buildable") is True
    assert result.get("reversible") is True
    assert result.get("verifiable") is True
    assert result.get("findings") == []
    assert result.get("facts_digest") == facts_digest
    assert result.get("opens_digest") == opens_digest


def test_audit_context_returns_snapshots_and_digests(tmp_path: Path):
    _drive_to_g4(tmp_path)
    facts_digest, opens_digest = _current_digests(tmp_path)
    code, result = _run_g4(tmp_path, "audit-context")
    assert code == 0, result
    assert result.get("facts_digest") == facts_digest
    assert result.get("opens_digest") == opens_digest
    assert "facts_snapshot" in result
    assert "opens_snapshot" in result


def test_delete_recompose_report_removes_file(tmp_path: Path):
    _drive_to_g4(tmp_path)
    _record_ok_recompose_report(tmp_path)
    report_path = g4_report_path(tmp_path)
    assert report_path.exists()

    code, result = _run_g4(tmp_path, "delete-recompose-report")
    assert code == 0, result
    assert result.get("deleted") is True
    assert not report_path.exists()


def test_gate_close_g4_requires_report(tmp_path: Path):
    _drive_to_g4(tmp_path)
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G4")
    assert code == 1
    assert "report" in result.get("error", "").lower() or "recompose" in result.get("error", "").lower()


def test_gate_close_g4_succeeds_with_ok_report(tmp_path: Path):
    _drive_to_g4(tmp_path)
    _record_ok_recompose_report(tmp_path)
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G4")
    assert code == 0, result
    assert result.get("closed") == "G4"


def test_gate_close_g4_rejects_findings(tmp_path: Path):
    _drive_to_g4(tmp_path)
    _record_ok_recompose_report(
        tmp_path,
        findings=[
            {
                "question": "Who owns retry?",
                "basis": "Two facts disagree",
                "blocking": True,
                "lens": "I",
            }
        ],
        buildable=False,
    )
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G4")
    assert code == 1
    assert "finding" in result.get("error", "").lower() or "buildable" in result.get("error", "").lower()


def test_gate_close_g4_ignores_caller_supplied_payload(tmp_path: Path):
    _drive_to_g4(tmp_path)
    forged = json.dumps(
        {
            "findings": [],
            "buildable": True,
            "reversible": True,
            "verifiable": True,
        }
    )
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G4", "--payload", forged)
    assert code == 1
    assert "report" in result.get("error", "").lower() or "recompose" in result.get("error", "").lower()


def test_record_recompose_report_rejects_unsourced_finding_lens(tmp_path: Path):
    _drive_to_g4(tmp_path)
    code, result = _record_ok_recompose_report(
        tmp_path,
        findings=[
            {
                "question": "Who owns retry?",
                "basis": "Two facts disagree",
                "blocking": True,
                "lens": "NOPE",
            }
        ],
        buildable=False,
    )
    assert code == 1
    assert "lens_tags" in result.get("error", "") or "source" in result.get("error", "")
