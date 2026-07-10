#!/usr/bin/env python3
"""Tests for inductive gate control facade and G2 subprocess boundaries."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_GATE_CTL = _INDUCTIVE_DIR / "inductive_gate_control.py"
_G2_CTL = _INDUCTIVE_DIR / "inductive_g2_control.py"
_G3_GROUNDING_CTL = _INDUCTIVE_DIR / "inductive_g3_grounding_control.py"
_G4_CTL = _INDUCTIVE_DIR / "inductive_g4_control.py"
_SECTION_CTL = _INDUCTIVE_DIR / "inductive_g3_section_control.py"

_PARENT_CONV = "11111111-1111-4111-8111-111111111111"
_SUBAGENT_CONV = "22222222-2222-4222-8222-222222222222"


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


def _run_g3_grounding(out_dir: Path, *args: str) -> tuple[int, dict]:
    res = subprocess.run(
        [sys.executable, str(_G3_GROUNDING_CTL), "--out-dir", str(out_dir), *args],
        capture_output=True,
        text=True,
    )
    try:
        payload = json.loads(res.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "raw": res.stdout, "stderr": res.stderr}
    return res.returncode, payload


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


def _seed_session(out_dir: Path) -> None:
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
            "--stage",
            "lulu-design",
            "--scope-ref",
            "approach/approach-doc.md",
            "--conversation-id",
            _PARENT_CONV,
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    index = json.loads(
        (out_dir / "inductive-scope" / "_index.json").read_text(encoding="utf-8")
    )
    assert index.get("profile") == "lulu-design"
    assert index.get("scope_ref") == "approach/approach-doc.md"


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


def _ok_g2_report() -> str:
    return json.dumps(
        {
            "verdict": "ok",
            "facts": ["Spine modules exist at expected topology level"],
            "divergences": [],
            "checklist": [],
            "produced_by": "subagent",
        }
    )


def _shape_breaking_g2_report() -> str:
    return json.dumps(
        {
            "verdict": "shape_breaking",
            "facts": [],
            "divergences": [
                {
                    "shape_claim": "Monolith entry",
                    "finding": "Observed microservice split contradicts spine",
                    "code_refs": ["svc/a/main.go"],
                }
            ],
            "checklist": [],
            "produced_by": "subagent",
        }
    )


def _grounding_receipt(section: str, sweep: int = 1) -> dict:
    return {
        "sweep": sweep,
        "mode": "shallow",
        "section": section,
        "frontier_kw": 0,
        "code_refs": ["main.js::init (L1-10)"],
        "facts": [f"{section} topology present"],
        "produced_by": "subagent",
    }


def _deep_grounding_receipt(section: str, ep_id: str, sweep: int = 1) -> dict:
    return {
        "sweep": sweep,
        "mode": "deep",
        "section": section,
        "ep_id": ep_id,
        "frontier_kw": 1,
        "code_refs": ["main.js::init (L12-18)"],
        "facts": [f"{section} {ep_id} concrete signature confirmed"],
        "produced_by": "subagent",
    }


def _record_ok_g2_report(tmp_path: Path) -> None:
    _run_g2(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-g2-report",
        "--json",
        _ok_g2_report(),
    )


def test_gate_close_g1_accepts_user_confirmed_without_architecture_view(tmp_path: Path):
    """Shape-confirm baseline is checkpoint; DQI architecture_view is optional."""
    _seed_session(tmp_path)
    code, result = _run_gate(
        tmp_path,
        "gate-close",
        "--gate",
        "G1",
        "--payload",
        json.dumps({"user_confirmed": True}),
    )
    assert code == 0, result
    assert result.get("closed") == "G1"
    index = json.loads((tmp_path / "inductive-scope" / "_index.json").read_text(encoding="utf-8"))
    assert index.get("last_checkpoint") == "shape"
    # best-effort: when tests run inside a git repo, SHA is recorded
    assert "checkpoint_git_sha" in index
    if index["checkpoint_git_sha"] is not None:
        assert len(index["checkpoint_git_sha"]) >= 7


def test_gate_close_g1_rejects_missing_user_confirmed(tmp_path: Path):
    _seed_session(tmp_path)
    code, result = _run_gate(
        tmp_path,
        "gate-close",
        "--gate",
        "G1",
        "--payload",
        json.dumps(
            {
                "architecture_view": {
                    "as_is": "a",
                    "to_be": "b",
                    "scope": {"in": ["x"], "out": []},
                    "spine": "s",
                    "traces_to": ["upstream"],
                }
            }
        ),
    )
    assert code != 0
    assert "user_confirmed" in str(result)


def test_resolve_context_reports_blocking_open_count(tmp_path: Path):
    _seed_session(tmp_path)
    code, payload = _run_section(tmp_path, "activate-section", "--section", "ST")
    assert code == 0, payload
    code, payload = _run_section(
        tmp_path,
        "add-open",
        "--section",
        "ST",
        "--kw",
        "2",
        "--trigger",
        "ai",
        "--means",
        "ai_scan",
        "--problem",
        "gap",
        "--blocking",
        "true",
    )
    assert code == 0, payload
    code, result = _run_gate(tmp_path, "resolve-context")
    assert code == 0, result
    assert result.get("active_gate") == "G1"
    assert result.get("active_section") == "ST"
    count = result.get("open_blocking_open_count")
    if count is None:
        count = result.get("open_blocking_ep_count")
    assert count == 1, result
    # DQI architecture_view is optional resume aid — absent until G1 writes it
    assert "architecture_view" in result


def test_g2_facade_check_forwards_success(tmp_path: Path):
    _seed_session(tmp_path)
    _run_gate(tmp_path, "gate-close", "--gate", "G1", "--payload", _g1_payload())
    _record_ok_g2_report(tmp_path)
    code, result = _run_gate(tmp_path, "g2-check-report")
    assert code == 0, result
    assert result.get("verdict") == "ok"


def test_g2_facade_list_forwards_summary(tmp_path: Path):
    _seed_session(tmp_path)
    _run_gate(tmp_path, "gate-close", "--gate", "G1", "--payload", _g1_payload())
    _record_ok_g2_report(tmp_path)
    code, result = _run_gate(tmp_path, "g2-list-report")
    assert code == 0, result
    assert result.get("verdict") == "ok"


def test_gate_close_accepts_hook_injected_conversation_id(tmp_path: Path):
    """hook_guard appends --conversation-id after subcommand args."""
    _seed_session(tmp_path)
    _run_gate(tmp_path, "gate-close", "--gate", "G1", "--payload", _g1_payload())
    _record_ok_g2_report(tmp_path)
    code, result = _run_gate(
        tmp_path,
        "gate-close",
        "--gate",
        "G2",
        "--conversation-id",
        _SUBAGENT_CONV,
    )
    assert code == 0, result
    assert result.get("closed") == "G2"


def test_g2_facade_check_shape_breaking_exit1_then_list_succeeds(tmp_path: Path):
    _seed_session(tmp_path)
    _run_gate(tmp_path, "gate-close", "--gate", "G1", "--payload", _g1_payload())
    _run_g2(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-g2-report",
        "--json",
        _shape_breaking_g2_report(),
    )

    check_code, check_result = _run_gate(tmp_path, "g2-check-report")
    assert check_code == 1
    assert check_result.get("ok") is False

    list_code, list_result = _run_gate(tmp_path, "g2-list-report")
    assert list_code == 0, list_result
    assert list_result.get("verdict") == "shape_breaking"
    assert len(list_result.get("divergences", [])) == 1


def test_gate_reopen_g1_facade_deletes_g2_report(tmp_path: Path):
    _seed_session(tmp_path)
    _run_gate(tmp_path, "gate-close", "--gate", "G1", "--payload", _g1_payload())
    _record_ok_g2_report(tmp_path)
    report_path = tmp_path / "g2-topology-report.json"
    assert report_path.exists()

    code, result = _run_gate(tmp_path, "gate-reopen", "--gate", "G1")
    assert code == 0, result
    assert result.get("deleted_g2_report") is True
    assert not report_path.exists()


def test_gate_reopen_g3_with_sections_rewinds_atomically(tmp_path: Path):
    _drive_single_section_to_g4(tmp_path)

    status_before = _run_section(tmp_path, "status")[1]
    assert status_before["sections"]["I"] == "cleared"

    code, result = _run_gate(tmp_path, "gate-reopen", "--gate", "G3", "--sections", "I")
    assert code == 0, result
    assert result.get("rewound_sections") == ["I"]
    assert result.get("active_gate") == "G3"

    status_after = _run_section(tmp_path, "status")[1]
    assert status_after["sections"]["I"] == "active"


def test_gate_reopen_sections_rejected_for_non_g3_gate(tmp_path: Path):
    _drive_single_section_to_g4(tmp_path)

    code, result = _run_gate(tmp_path, "gate-reopen", "--gate", "G1", "--sections", "I")
    assert code != 0
    assert "G3" in str(result.get("error", ""))


def test_gate_reopen_g3_without_sections_leaves_sections_untouched(tmp_path: Path):
    _drive_single_section_to_g4(tmp_path)

    code, result = _run_gate(tmp_path, "gate-reopen", "--gate", "G3")
    assert code == 0, result
    assert result.get("rewound_sections") == []

    status_after = _run_section(tmp_path, "status")[1]
    assert status_after["sections"]["I"] == "cleared"


def test_grounding_facade_check_forwards_success(tmp_path: Path):
    _seed_session(tmp_path)
    payload = json.dumps([_grounding_receipt("I"), _grounding_receipt("ST")])
    record_code, record_result = _run_g3_grounding(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        payload,
    )
    assert record_code == 0, record_result

    code, result = _run_gate(tmp_path, "grounding-check", "--sweep", "1")
    assert code == 0, result
    assert result.get("unsettled_count") == 2


def test_grounding_facade_list_forwards_receipts(tmp_path: Path):
    _seed_session(tmp_path)
    payload = json.dumps([_grounding_receipt("I"), _grounding_receipt("ST")])
    _run_g3_grounding(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        payload,
    )

    code, result = _run_gate(tmp_path, "grounding-list", "--sweep", "1")
    assert code == 0, result
    assert result.get("count") == 2
    sections = {r["section"] for r in result.get("receipts", [])}
    assert sections == {"I", "ST"}


def test_deep_grounding_list_facade_forwards_single_point_receipt(tmp_path: Path):
    _seed_session(tmp_path)
    _run_g3_grounding(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        json.dumps(_deep_grounding_receipt("I", "EP-001")),
    )
    _run_g3_grounding(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-grounding",
        "--sweep",
        "1",
        "--json",
        json.dumps(_deep_grounding_receipt("I", "EP-002")),
    )

    code, result = _run_gate(tmp_path, "deep-grounding-list", "--sweep", "1", "--ep-id", "EP-001")
    assert code == 0, result
    assert result.get("count") == 1
    assert result["receipts"][0]["ep_id"] == "EP-001"


def test_deep_grounding_list_facade_requires_ep_id(tmp_path: Path):
    _seed_session(tmp_path)
    code, result = _run_gate(tmp_path, "deep-grounding-list", "--sweep", "1")
    assert code != 0
    assert "ep-id" in str(result).lower()


def test_gate_close_g2_uses_subprocess_not_import(tmp_path: Path):
    _seed_session(tmp_path)
    _run_gate(tmp_path, "gate-close", "--gate", "G1", "--payload", _g1_payload())
    _record_ok_g2_report(tmp_path)
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G2")
    assert code == 0, result
    assert result.get("closed") == "G2"


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


def _drive_single_section_to_g4(tmp_path: Path) -> None:
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
    _record_ok_g2_report(tmp_path)
    code, _ = _run_gate(tmp_path, "gate-close", "--gate", "G2")
    assert code == 0

    _run_section(tmp_path, "activate-section", "--section", "I")
    _run_section(tmp_path, "seed-decision", "--section", "I", "--kw", "1", "--text", "Body text.")
    _run_section(tmp_path, "set-frontier", "--section", "I", "--kw", "3")
    code, result = _run_section(tmp_path, "clear-section", "--section", "I")
    assert code == 0, result

    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G3")
    assert code == 0, result


def _record_ok_recompose_report(tmp_path: Path) -> None:
    _run_g4(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-recompose-report",
        "--json",
        json.dumps(_ok_recompose_report()),
    )


def test_g4_facade_check_forwards_success(tmp_path: Path):
    _drive_single_section_to_g4(tmp_path)
    _record_ok_recompose_report(tmp_path)
    code, result = _run_gate(tmp_path, "g4-check-report")
    assert code == 0, result
    assert result.get("closable") is True


def test_g4_facade_list_forwards_summary(tmp_path: Path):
    _drive_single_section_to_g4(tmp_path)
    _record_ok_recompose_report(tmp_path)
    code, result = _run_gate(tmp_path, "g4-list-report")
    assert code == 0, result
    assert result.get("buildable") is True


def test_g4_facade_check_unresolved_conflict_exit1_then_list_succeeds(tmp_path: Path):
    _drive_single_section_to_g4(tmp_path)
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

    check_code, check_result = _run_gate(tmp_path, "g4-check-report")
    assert check_code == 1
    assert check_result.get("ok") is False

    list_code, list_result = _run_gate(tmp_path, "g4-list-report")
    assert list_code == 0, list_result
    assert len(list_result.get("conflicts", [])) == 1


def test_gate_close_g4_uses_subprocess_not_import(tmp_path: Path):
    _drive_single_section_to_g4(tmp_path)
    _record_ok_recompose_report(tmp_path)
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G4")
    assert code == 0, result
    assert result.get("closed") == "G4"
