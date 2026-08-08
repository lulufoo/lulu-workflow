#!/usr/bin/env python3
"""Tests for inductive G4 semantic recompose report control + gate-close G4."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_G4_CTL = _INDUCTIVE_DIR / "inductive_g4_control.py"
_GATE_CTL = _INDUCTIVE_DIR / "inductive_gate_control.py"
_SECTION_CTL = _INDUCTIVE_DIR / "inductive_g3_section_control.py"

_PARENT_CONV = "11111111-1111-4111-8111-111111111111"
_SUBAGENT_CONV = "22222222-2222-4222-8222-222222222222"

sys.path.insert(0, str(_INDUCTIVE_DIR))
from g4_recompose_report_schema import MAX_FACTS, validate_report  # noqa: E402



def _g2_close_payload() -> str:
    return (
        '{"topic_loop_done": true, "design_goal_met": true, '
        '"human_exit_confirmed": true, "topic_exit": "cleared"}'
    )


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


def _run_section(out_dir: Path, *args: str) -> tuple[int, dict]:
    res = subprocess.run(
        [sys.executable, str(_SECTION_CTL), "--out-dir", str(out_dir), *args],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(res.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "raw": res.stdout, "stderr": res.stderr}
    return res.returncode, payload


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



def _ok_recompose_report(**overrides) -> dict:
    base = {
        "conflicts": [],
        "buildable": True,
        "reversible": True,
        "verifiable": True,
        "facts": ["No cross-section conflicts observed"],
        "produced_by": "subagent",
    }
    base.update(overrides)
    return base


def _drive_to_g4(tmp_path: Path) -> None:
    """Seed a single-section session and close G1/G2/G3 for real, leaving G4 active."""
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
            "--cycle-id",
            "c1",
            "--conversation-id",
            _PARENT_CONV,
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr

    code, _ = _run_gate(tmp_path, "gate-close", "--gate", "G1", "--payload", _g1_payload())
    assert code == 0

    _g2_prepare_exit(tmp_path)
    code, _ = _run_gate(tmp_path, "gate-close", "--gate", "G2", "--payload", _g2_close_payload())
    assert code == 0

    code, _ = _run_section(tmp_path, "activate-section", "--section", "I")
    assert code == 0
    code, _ = _run_section(
        tmp_path,
        "seed-decision",
        "--section",
        "I",
        "--lens-tags",
        "I",
        "--kw",
        "1",
        "--text",
        "Body text.",
    )
    assert code == 0
    code, _ = _run_section(tmp_path, "set-frontier", "--section", "I", "--kw", "3")
    assert code == 0
    code, _ = _run_section(tmp_path, "clear-section", "--section", "I")
    assert code == 0

    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G3")
    assert code == 0, result


def _record_ok_recompose_report(tmp_path: Path) -> tuple[int, dict]:
    return _run_g4(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-recompose-report",
        "--json",
        json.dumps(_ok_recompose_report()),
    )


def test_validate_report_requires_bool_predicates():
    errors = validate_report(
        {
            "version": "1",
            "conflicts": [],
            "buildable": "yes",
            "reversible": True,
            "verifiable": True,
            "facts": [],
            "produced_by": "subagent",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert any("buildable" in e for e in errors)


def test_validate_report_requires_facts_when_clean():
    errors = validate_report(
        {
            "version": "1",
            "conflicts": [],
            "buildable": True,
            "reversible": True,
            "verifiable": True,
            "facts": [],
            "produced_by": "subagent",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert any("clean verdict" in e for e in errors)


def test_validate_report_allows_empty_facts_when_not_clean():
    errors = validate_report(
        {
            "version": "1",
            "conflicts": [],
            "buildable": False,
            "reversible": True,
            "verifiable": True,
            "facts": [],
            "produced_by": "subagent",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert not any("clean verdict" in e for e in errors)


def test_validate_report_rejects_conflict_with_owning_section_not_in_sections():
    errors = validate_report(
        {
            "version": "1",
            "conflicts": [
                {
                    "description": "Section A assumes B owns X, B disagrees",
                    "sections": ["A", "B"],
                    "owning_section": "C",
                }
            ],
            "buildable": True,
            "reversible": True,
            "verifiable": True,
            "facts": [],
            "produced_by": "subagent",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )
    assert any("owning_section" in e for e in errors)


def test_record_recompose_report_blocks_parent_conversation(tmp_path: Path):
    _drive_to_g4(tmp_path)
    code, result = _run_g4(
        tmp_path,
        "--conversation-id",
        _PARENT_CONV,
        "record-recompose-report",
        "--json",
        json.dumps(_ok_recompose_report()),
    )
    assert code == 1
    assert "SUBAGENT_REQUIRED" in result.get("error", "")


def test_record_recompose_report_allows_subagent(tmp_path: Path):
    _drive_to_g4(tmp_path)
    code, result = _record_ok_recompose_report(tmp_path)
    assert code == 0, result


def test_check_recompose_report_passes_when_closable(tmp_path: Path):
    _drive_to_g4(tmp_path)
    _record_ok_recompose_report(tmp_path)
    code, result = _run_g4(tmp_path, "check-recompose-report")
    assert code == 0, result
    assert result.get("closable") is True


def test_check_recompose_report_fails_on_unresolved_conflict(tmp_path: Path):
    _drive_to_g4(tmp_path)
    conflicting = _ok_recompose_report(
        conflicts=[
            {
                "description": "I and ST disagree on ownership of the retry policy",
                "sections": ["I", "ST"],
                "owning_section": None,
            }
        ],
    )
    _run_g4(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-recompose-report",
        "--json",
        json.dumps(conflicting),
    )
    code, result = _run_g4(tmp_path, "check-recompose-report")
    assert code == 1
    assert "conflict" in result.get("error", "").lower()


def test_list_recompose_report_returns_summary(tmp_path: Path):
    _drive_to_g4(tmp_path)
    _record_ok_recompose_report(tmp_path)
    code, result = _run_g4(tmp_path, "list-recompose-report")
    assert code == 0, result
    assert result.get("buildable") is True
    assert result.get("conflicts") == []


def test_delete_recompose_report_removes_file(tmp_path: Path):
    _drive_to_g4(tmp_path)
    _record_ok_recompose_report(tmp_path)
    report_path = tmp_path / "g4-recompose-report.json"
    assert report_path.exists()

    code, result = _run_g4(tmp_path, "delete-recompose-report")
    assert code == 0, result
    assert result.get("deleted") is True
    assert not report_path.exists()


def test_gate_close_g4_requires_report(tmp_path: Path):
    _drive_to_g4(tmp_path)
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G4")
    assert code == 1
    assert "recompose" in result.get("error", "").lower()


def test_gate_close_g4_succeeds_with_ok_report(tmp_path: Path):
    _drive_to_g4(tmp_path)
    _record_ok_recompose_report(tmp_path)
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G4")
    assert code == 0, result
    assert result.get("closed") == "G4"


def test_gate_close_g4_rejects_unresolved_conflicts(tmp_path: Path):
    _drive_to_g4(tmp_path)
    conflicting = _ok_recompose_report(
        conflicts=[
            {
                "description": "I and ST disagree on ownership of the retry policy",
                "sections": ["I", "ST"],
                "owning_section": None,
            }
        ],
    )
    _run_g4(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-recompose-report",
        "--json",
        json.dumps(conflicting),
    )
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G4")
    assert code == 1
    assert "conflict" in result.get("error", "").lower()


def test_gate_close_g4_ignores_caller_supplied_payload(tmp_path: Path):
    """G4 is report-driven: a forged --payload claiming success must not bypass the missing report."""
    _drive_to_g4(tmp_path)
    forged = json.dumps(
        {
            "reforms_shape": True,
            "shape_absorbed": True,
            "conflicts": [],
            "buildable": True,
            "reversible": True,
            "verifiable": True,
        }
    )
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G4", "--payload", forged)
    assert code == 1
    assert "recompose" in result.get("error", "").lower()


def test_gate_close_g4_forged_payload_cannot_override_real_conflicts(tmp_path: Path):
    """Stronger anti-forgery case: a real conflicting report is on disk; a forged
    all-clean --payload must not be able to paper over it."""
    _drive_to_g4(tmp_path)
    conflicting = _ok_recompose_report(
        conflicts=[
            {
                "description": "I and ST disagree on ownership of the retry policy",
                "sections": ["I", "ST"],
                "owning_section": None,
            }
        ],
    )
    _run_g4(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-recompose-report",
        "--json",
        json.dumps(conflicting),
    )

    forged = json.dumps(
        {
            "reforms_shape": True,
            "shape_absorbed": True,
            "conflicts": [],
            "buildable": True,
            "reversible": True,
            "verifiable": True,
        }
    )
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G4", "--payload", forged)
    assert code == 1
    assert "conflict" in result.get("error", "").lower()


def test_gate_reopen_g3_deletes_g4_report(tmp_path: Path):
    _drive_to_g4(tmp_path)
    _record_ok_recompose_report(tmp_path)
    report_path = tmp_path / "g4-recompose-report.json"
    assert report_path.exists()

    code, result = _run_gate(tmp_path, "gate-reopen", "--gate", "G3")
    assert code == 0, result
    assert result.get("deleted_g4_report") is True
    assert not report_path.exists()


def test_schema_max_facts_constant():
    assert MAX_FACTS == 8
