#!/usr/bin/env python3
"""Tests for inductive G4 internal-audit report control + gate-close G4."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_G4_CTL = _INDUCTIVE_DIR / "recompose" / "inductive_recompose_control.py"
_GATE_CTL = _INDUCTIVE_DIR / "inductive_gate_control.py"
_KERNEL = Path(__file__).resolve().parent.parent / "_kernel"

sys.path.insert(0, str(_INDUCTIVE_DIR / "open-point"))
sys.path.insert(0, str(_INDUCTIVE_DIR / "recompose"))
sys.path.insert(0, str(_INDUCTIVE_DIR))
for _name in ("gate", "topic", "open-point", "recompose"):
    sys.path.insert(0, str(_INDUCTIVE_DIR / "schema" / _name))
sys.path.insert(0, str(_KERNEL))

from compose_state_lock import canonical_digest  # noqa: E402
from recompose_report_schema import recompose_report_path  # noqa: E402
from lens_frontier_schema import (  # noqa: E402
    default_lens_entry,
    lens_frontier_path,
    load_lens_frontier,
)
from open_point_store import (  # noqa: E402
    add_opens,
    ensure_frontier,
    frontier_skip,
    lens_snapshot,
    registry_lens_keys,
)

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


_DESIGN_PROFILE = (
    Path(__file__).resolve().parents[3] / "lulu-design" / "compose-profile.json"
)
_KEEP_LENSES = frozenset({"I"})


def _bind_skill_fixture(out_dir: Path) -> str:
    digest = hashlib.sha256(_DESIGN_PROFILE.read_bytes()).hexdigest()
    (Path(out_dir) / "session-state.md").write_text(
        "---\n"
        "version: 2\n"
        "active_doc: 2\n"
        f"profile_path: {_DESIGN_PROFILE.resolve()}\n"
        f"profile_digest: {digest}\n"
        "start_id: test\n"
        "holder_finalized: true\n"
        "updated_at: 2024-01-01T00:00:00+00:00\n"
        "---\n",
        encoding="utf-8",
    )
    return str(Path(out_dir).resolve())


def _isolate_lenses(slice_dir: Path, project_root: str) -> None:
    ensure_frontier(slice_dir, project_root)
    for lens in registry_lens_keys(lens_snapshot(slice_dir, project_root)):
        if lens not in _KEEP_LENSES:
            frontier_skip(slice_dir, lens, "test isolate", project_root)


def _run_gate(out_dir: Path, *args: str) -> tuple[int, dict]:
    argv = [sys.executable, str(_GATE_CTL), "--out-dir", str(out_dir)]
    if "G3" in args and "--project-root" not in args:
        argv.extend(["--project-root", _bind_skill_fixture(out_dir)])
    argv.extend(args)
    res = subprocess.run(
        argv,
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
    _isolate_lenses(slice_dir, _bind_skill_fixture(slice_dir))
    (slice_dir / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-seed", "text": "g4 lens source", "lens_tags": ["I"]}]
        )
        + "\n",
        encoding="utf-8",
    )


def _detect_meta(slice_dir: Path, raw_candidates):
    root = _bind_skill_fixture(slice_dir)
    _isolate_lenses(slice_dir, root)
    path = lens_frontier_path(slice_dir)
    frontier_lenses = load_lens_frontier(path)["lenses"] if path.is_file() else {}
    raw = list(raw_candidates)
    checked = registry_lens_keys(lens_snapshot(slice_dir, root))
    hit = {
        str(item.get("lens", "")).strip().upper()
        for item in raw
        if isinstance(item, dict) and item.get("lens")
    }
    measurements = []
    for lens in checked:
        key = str(lens).strip().upper()
        entry = frontier_lenses.get(key) or default_lens_entry()
        start = int(entry.get("frontier_kw") or 0)
        measurements.append(
            {"lens": key, "start_kw": start, "gap_kw": start if key in hit else None}
        )
    return {
        "checked_lenses": checked,
        "raw_candidates": raw,
        "lens_measurements": measurements,
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
    _g2_prepare_exit(tmp_path)
    code, result = _run_gate(
        tmp_path, "gate-close", "--gate", "G2", "--payload", _g2_close_payload()
    )
    assert code == 0, result
    _ready_cleared(tmp_path)
    add_opens(
        tmp_path,
        opens=[],
        detect=_detect_meta(tmp_path, []),
        project_root=_bind_skill_fixture(tmp_path),
    )
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
    report_path = recompose_report_path(tmp_path)
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
