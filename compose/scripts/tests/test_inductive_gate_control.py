#!/usr/bin/env python3
"""Tests for inductive gate control facade and Topic Loop G2 close."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_REPO = Path(__file__).resolve().parents[4]
_GATE_CTL = _INDUCTIVE_DIR / "inductive_gate_control.py"
_DESIGN_DOMAIN = (
    _REPO / "lulu-dev-workflow" / "lulu-design" / "templates" / "domain-instance.json"
)
_G4_CTL = _INDUCTIVE_DIR / "inductive_g4_control.py"
_KERNEL = Path(__file__).resolve().parent.parent / "_kernel"

sys.path.insert(0, str(_INDUCTIVE_DIR))
for _name in ("gate", "g2", "g3", "g4"):
    sys.path.insert(0, str(_INDUCTIVE_DIR / "schema" / _name))
sys.path.insert(0, str(_KERNEL))

from compose_state_lock import canonical_digest  # noqa: E402
from g4_recompose_report_schema import g4_report_path, load_report  # noqa: E402
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
    load_bundle,
    registry_lens_keys,
)
from opens_schema import load_opens, opens_path  # noqa: E402

_PARENT_CONV = "11111111-1111-4111-8111-111111111111"
_SUBAGENT_CONV = "22222222-2222-4222-8222-222222222222"


def _g2_close_payload(topic_exit: str = "cleared") -> str:
    return (
        '{"topic_loop_done": true, "design_goal_met": true, '
        f'"human_exit_confirmed": true, "topic_exit": "{topic_exit}"}}'
    )


def _g2_prepare_exit(
    out_dir: Path,
    *,
    result: str = "cleared",
    gap_remaining: int = 0,
) -> None:
    code, payload = _run_gate(
        out_dir,
        "record-topic-landscape",
        "--purpose",
        "pre_close",
        "--gap-remaining",
        str(gap_remaining),
    )
    assert code == 0, payload
    code, payload = _run_gate(
        out_dir,
        "record-g2-topic-exit",
        "--result",
        result,
        "--human-confirmed",
    )
    assert code == 0, payload


_DESIGN_PROFILE = (
    _REPO / "lulu-dev-workflow" / "lulu-design" / "compose-profile.json"
)
_KEEP_LENSES = frozenset({"I", "ST"})


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
    if "resolve-context" in args and "--project-root" not in args:
        argv.extend(["--project-root", str(_REPO)])
    elif "G3" in args and "--project-root" not in args:
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


def _seed_session(out_dir: Path) -> None:
    res = subprocess.run(
        [
            sys.executable,
            str(_GATE_CTL),
            "--out-dir",
            str(out_dir),
            "init-session",
            "--cycle-id",
            "c1",
            "--stage",
            "lulu-design",
            "--conversation-id",
            _PARENT_CONV,
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr


def _json_or_empty(path: Path):
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _current_digests(slice_dir: Path) -> tuple[str, str]:
    facts = _json_or_empty(slice_dir / "_facts.json")
    opens = _json_or_empty(slice_dir / "inductive-opens.json")
    return canonical_digest(facts), canonical_digest(opens)


def _ready_cleared(slice_dir: Path) -> None:
    _isolate_lenses(slice_dir, _bind_skill_fixture(slice_dir))
    (slice_dir / "_facts.json").write_text(
        json.dumps(
            [{"id": "F-seed", "text": "g4 lens source", "lens_tags": ["I"]}]
        )
        + "\n",
        encoding="utf-8",
    )


def _detect_meta(slice_dir: Path, raw_candidates, **overrides):
    root = _bind_skill_fixture(slice_dir)
    _isolate_lenses(slice_dir, root)
    path = lens_frontier_path(slice_dir)
    frontier_lenses = load_lens_frontier(path)["lenses"] if path.is_file() else {}
    raw = list(raw_candidates)
    checked = overrides.get("checked_lenses") or registry_lens_keys(
        lens_snapshot(slice_dir, root)
    )
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
    meta = {
        "checked_lenses": checked,
        "raw_candidates": raw,
        "lens_measurements": measurements,
    }
    meta.update(overrides)
    return meta


def _human_open(**overrides):
    base = {
        "question": "What is unresolved?",
        "basis": "Dialogue exposed a gap",
        "blocking": True,
        "source": {"actor": "human", "means": "direct"},
        "lens": "I",
    }
    base.update(overrides)
    return base


def _close_g2(out_dir: Path) -> None:
    _g2_prepare_exit(out_dir, result="cleared", gap_remaining=0)
    code, result = _run_gate(
        out_dir, "gate-close", "--gate", "G2", "--payload", _g2_close_payload()
    )
    assert code == 0, result


def _drive_to_g3(out_dir: Path) -> None:
    _seed_session(out_dir)
    _close_g2(out_dir)


def _drive_to_g4(out_dir: Path) -> None:
    _drive_to_g3(out_dir)
    _ready_cleared(out_dir)
    add_opens(
        out_dir,
        opens=[],
        detect=_detect_meta(out_dir, []),
        project_root=_bind_skill_fixture(out_dir),
    )
    code, result = _run_gate(
        out_dir, "gate-close", "--gate", "G3", "--mode", "cleared", "--confirm"
    )
    assert code == 0, result


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


def _record_ok_recompose_report(out_dir: Path, **overrides) -> tuple[int, dict]:
    return _run_g4(
        out_dir,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-recompose-report",
        "--json",
        json.dumps(_ok_recompose_report(out_dir, **overrides)),
    )


def _report_digest(out_dir: Path) -> str:
    return canonical_digest(load_report(g4_report_path(out_dir)))


def test_init_session_fills_gate_stage_from_revision_pointer(tmp_path: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_kernel"))
    from workflow_paths import (  # noqa: WPS433
        seed_revision_profile_pointer,
        write_active_profile,
    )

    rev = tmp_path / "revision1"
    rev.mkdir()
    seed_revision_profile_pointer(rev, "lulu-design")
    write_active_profile(tmp_path, "c1", "lulu-design")
    code, payload = _run_gate(
        rev,
        "--project-root",
        str(tmp_path),
        "init-session",
        "--cycle-id",
        "c1",
        "--conversation-id",
        _PARENT_CONV,
    )
    assert code == 0, payload
    gate = json.loads((rev / "inductive-gate-state.json").read_text(encoding="utf-8"))
    assert gate.get("stage") == "lulu-design"


def test_init_session_starts_at_g2(tmp_path: Path) -> None:
    _seed_session(tmp_path)
    code, result = _run_gate(tmp_path, "resolve-context")
    assert code == 0, result
    assert result.get("active_gate") == "G2"
    assert result.get("gates", {}).get("G2") == "active"
    assert "G1" not in (result.get("gates") or {})


def test_gate_close_g1_is_rejected(tmp_path: Path) -> None:
    _seed_session(tmp_path)
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G1")
    assert code != 0
    assert "invalid gate" in str(result).lower() or "g1" in str(result).lower()


def test_load_active_gate_g1_is_incompatible(tmp_path: Path) -> None:
    sys.path.insert(0, str(_INDUCTIVE_DIR))
    from inductive_gate_state_schema import (  # noqa: WPS433
        init_gate_state,
        load_gate_state,
        save_gate_state,
        validate_gate_state,
    )

    path = tmp_path / "inductive-gate-state.json"
    state = init_gate_state(cycle_id="c1", stage="lulu-design")
    save_gate_state(path, state)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["active_gate"] = "G1"
    raw["gates"]["G1"] = {"status": "active", "closed_at": None, "payload": None}
    path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="G1 is retired"):
        load_gate_state(path)
    errors = validate_gate_state(raw)
    assert any("G1 is retired" in item for item in errors)


def test_resolve_context_reports_open_point_idle_zeros(tmp_path: Path) -> None:
    _seed_session(tmp_path)
    code, result = _run_gate(tmp_path, "resolve-context")
    assert code == 0, result
    assert result.get("active_gate") == "G2"
    assert "gates" in result
    open_point = result.get("open_point") or {}
    assert open_point.get("phase") == "idle"
    assert open_point.get("active_batch_id") is None
    assert open_point.get("active_open_id") is None
    assert open_point.get("open_count") == 0


def test_resolve_context_includes_guide_d1_d2(tmp_path: Path) -> None:
    _seed_session(tmp_path)
    code, result = _run_gate(tmp_path, "resolve-context")
    assert code == 0, result
    domain = json.loads(_DESIGN_DOMAIN.read_text(encoding="utf-8"))
    guide = result.get("guide") or {}
    assert guide.get("cognitive_frame") == domain["cognitive_frame"]
    assert guide.get("intent_anchor") == domain["intent_anchor"]
    assert set(guide) == {"cognitive_frame", "intent_anchor"}


def test_resolve_context_fails_without_project_root(tmp_path: Path) -> None:
    _seed_session(tmp_path)
    code, result = _run_gate(tmp_path, "--project-root", "", "resolve-context")
    assert code != 0
    assert "project-root" in str(result.get("error", "")).lower()


def test_resolve_context_fails_when_stage_empty(tmp_path: Path) -> None:
    gate_path = tmp_path / "inductive-gate-state.json"
    gate_path.write_text(
        json.dumps(
            {
                "version": "1",
                "cycle_id": "c1",
                "stage": "",
                "active_gate": "G2",
                "gates": {
                    "G2": {"status": "active", "closed_at": None, "payload": None},
                    "G3": {"status": "pending", "closed_at": None, "payload": None},
                    "G4": {"status": "pending", "closed_at": None, "payload": None},
                },
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    code, result = _run_gate(tmp_path, "resolve-context")
    assert code != 0
    assert "stage" in str(result.get("error", "")).lower()


def test_resolve_context_fails_when_domain_unresolved(tmp_path: Path) -> None:
    _seed_session(tmp_path)
    gate_path = tmp_path / "inductive-gate-state.json"
    raw = json.loads(gate_path.read_text(encoding="utf-8"))
    raw["stage"] = "not-a-compose-profile"
    gate_path.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
    code, result = _run_gate(tmp_path, "resolve-context")
    assert code != 0
    error = str(result.get("error", "")).lower()
    assert "guide" in error or "profile" in error or "domain" in error


def test_gate_close_accepts_hook_injected_conversation_id(tmp_path: Path):
    """hook_guard appends --conversation-id after subcommand args."""
    _seed_session(tmp_path)
    _g2_prepare_exit(tmp_path, result="cleared", gap_remaining=0)
    code, result = _run_gate(
        tmp_path,
        "gate-close",
        "--gate",
        "G2",
        "--payload",
        _g2_close_payload(),
        "--conversation-id",
        _SUBAGENT_CONV,
    )
    assert code == 0, result
    assert result.get("closed") == "G2"


def test_gate_reopen_g3_sections_is_rejected(tmp_path: Path) -> None:
    _drive_to_g4(tmp_path)
    code, result = _run_gate(tmp_path, "gate-reopen", "--gate", "G3", "--sections", "I")
    assert code != 0
    assert "sections" in str(result).lower()


def test_gate_reopen_g3_without_from_report_fails(tmp_path: Path) -> None:
    _drive_to_g4(tmp_path)
    code, result = _run_gate(tmp_path, "gate-reopen", "--gate", "G3")
    assert code != 0
    assert "from-report" in str(result).lower()


def test_gate_reopen_g3_from_report_registers_findings_and_deletes_report(
    tmp_path: Path,
) -> None:
    _drive_to_g4(tmp_path)
    finding = {
        "question": "Who owns retry?",
        "basis": "Two facts disagree on ownership",
        "blocking": True,
        "lens": "I",
    }
    code, recorded = _record_ok_recompose_report(
        tmp_path,
        findings=[finding],
        buildable=False,
    )
    assert code == 0, recorded
    digest = recorded.get("report_digest") or _report_digest(tmp_path)
    report_path = g4_report_path(tmp_path)
    assert report_path.is_file()

    code, result = _run_gate(
        tmp_path,
        "gate-reopen",
        "--gate",
        "G3",
        "--from-report",
        "--report-digest",
        digest,
    )
    assert code == 0, result
    assert result.get("reopened") == "G3"
    assert result.get("active_gate") == "G3"
    assert not report_path.exists()
    opens = load_opens(opens_path(tmp_path))
    assert len(opens) == 1
    assert opens[0]["question"] == finding["question"]
    assert opens[0]["basis"] == finding["basis"]
    assert opens[0]["blocking"] is True
    assert opens[0]["source"] == {"actor": "ai", "means": "audit"}
    bundle = load_bundle(tmp_path)
    assert bundle["state"]["phase"] == "processing"
    assert bundle["state"]["active_open_id"] == opens[0]["id"]


def test_gate_reopen_g2_deletes_g4_report(tmp_path: Path) -> None:
    _drive_to_g4(tmp_path)
    code, recorded = _record_ok_recompose_report(tmp_path)
    assert code == 0, recorded
    report_path = g4_report_path(tmp_path)
    assert report_path.is_file()
    code, result = _run_gate(tmp_path, "gate-reopen", "--gate", "G2")
    assert code == 0, result
    assert result.get("reopened") == "G2"
    assert result.get("active_gate") == "G2"
    assert result.get("deleted_g4_report") is True
    assert not report_path.exists()


def test_gate_close_g2_topic_loop_payload(tmp_path: Path):
    _seed_session(tmp_path)
    code, result = _run_gate(tmp_path, "resolve-context")
    assert code == 0, result
    assert "Topic Loop" in str(result.get("gate_symbols", {}).get("G2", ""))
    _g2_prepare_exit(tmp_path, result="cleared", gap_remaining=0)
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G2", "--payload", _g2_close_payload())
    assert code == 0, result
    assert result.get("closed") == "G2"


def test_gate_close_g2_requires_topic_exit(tmp_path: Path):
    _seed_session(tmp_path)
    bare = (
        '{"topic_loop_done": true, "design_goal_met": true, '
        '"human_exit_confirmed": true}'
    )
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G2", "--payload", bare)
    assert code != 0
    assert "topic_exit" in str(result).lower()


def test_gate_close_g2_rejects_missing_exit_receipt(tmp_path: Path):
    _seed_session(tmp_path)
    code, result = _run_gate(
        tmp_path, "gate-close", "--gate", "G2", "--payload", _g2_close_payload(),
    )
    assert code != 0
    assert "exit" in str(result).lower() or "landscape" in str(result).lower()


def test_gate_close_g2_rejects_cleared_with_remaining_gaps(tmp_path: Path):
    _seed_session(tmp_path)
    code, payload = _run_gate(
        tmp_path,
        "record-topic-landscape",
        "--purpose",
        "pre_close",
        "--gap-remaining",
        "2",
    )
    assert code == 0, payload
    code, payload = _run_gate(
        tmp_path,
        "record-g2-topic-exit",
        "--result",
        "cleared",
        "--human-confirmed",
    )
    assert code != 0
    assert "gap_remaining" in str(payload).lower()


def test_gate_close_g2_rejects_seek_purpose_for_close(tmp_path: Path):
    _seed_session(tmp_path)
    code, payload = _run_gate(
        tmp_path,
        "record-topic-landscape",
        "--purpose",
        "seek",
        "--gap-remaining",
        "0",
    )
    assert code == 0, payload
    code, payload = _run_gate(
        tmp_path,
        "record-g2-topic-exit",
        "--result",
        "cleared",
        "--human-confirmed",
    )
    assert code != 0
    assert "pre_close" in str(payload).lower()


def test_gate_close_g2_accepts_hard_skip_topic_exit(tmp_path: Path):
    _seed_session(tmp_path)
    _g2_prepare_exit(tmp_path, result="hard_skip", gap_remaining=2)
    code, result = _run_gate(
        tmp_path,
        "gate-close",
        "--gate",
        "G2",
        "--payload",
        _g2_close_payload("hard_skip"),
    )
    assert code == 0, result
    assert result.get("closed") == "G2"


def test_gate_close_g3_requires_mode_and_confirm(tmp_path: Path) -> None:
    _drive_to_g3(tmp_path)
    add_opens(
        tmp_path,
        opens=[],
        detect=_detect_meta(tmp_path, []),
        project_root=_bind_skill_fixture(tmp_path),
    )
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G3")
    assert code != 0
    assert "mode" in str(result).lower() or "confirm" in str(result).lower()
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G3", "--mode", "cleared")
    assert code != 0
    assert "confirm" in str(result).lower()


def test_gate_close_g3_cleared_requires_fresh_zero_result_and_no_opens(
    tmp_path: Path,
) -> None:
    _drive_to_g3(tmp_path)
    code, result = _run_gate(
        tmp_path, "gate-close", "--gate", "G3", "--mode", "cleared", "--confirm"
    )
    assert code != 0

    add_opens(
        tmp_path,
        opens=[_human_open(blocking=False)],
        project_root=_bind_skill_fixture(tmp_path),
    )
    code, result = _run_gate(
        tmp_path, "gate-close", "--gate", "G3", "--mode", "cleared", "--confirm"
    )
    assert code != 0
    bundle = load_bundle(tmp_path)
    assert any(item.get("status") == "open" for item in bundle["opens"])
    assert bundle["state"]["phase"] == "processing"


def test_gate_close_g3_cleared_succeeds_on_fresh_zero_result(tmp_path: Path) -> None:
    _drive_to_g4(tmp_path)
    state = json.loads((tmp_path / "inductive-gate-state.json").read_text(encoding="utf-8"))
    assert state["gates"]["G3"]["status"] == "closed"
    assert state["active_gate"] == "G4"


def test_gate_close_g3_hard_skip_abandons_batch_and_allows_nonblocking(
    tmp_path: Path,
) -> None:
    _drive_to_g3(tmp_path)
    add_opens(
        tmp_path,
        opens=[_human_open(blocking=False)],
        project_root=_bind_skill_fixture(tmp_path),
    )
    bundle_before = load_bundle(tmp_path)
    assert bundle_before["state"]["phase"] == "processing"
    code, result = _run_gate(
        tmp_path, "gate-close", "--gate", "G3", "--mode", "hard-skip", "--confirm"
    )
    assert code == 0, result
    assert result.get("closed") == "G3"
    bundle = load_bundle(tmp_path)
    assert bundle["state"]["phase"] == "idle"
    assert bundle["state"]["active_batch_id"] is None
    assert bundle["batches"]["batches"][0]["status"] == "abandoned"
    assert any(
        item.get("status") == "open" and item.get("blocking") is False
        for item in bundle["opens"]
    )


def test_g4_record_rejects_stale_facts_or_opens_digest(tmp_path: Path) -> None:
    _drive_to_g4(tmp_path)
    stale = _ok_recompose_report(tmp_path, facts_digest="0" * 64)
    code, result = _run_g4(
        tmp_path,
        "--conversation-id",
        _SUBAGENT_CONV,
        "record-recompose-report",
        "--json",
        json.dumps(stale),
    )
    assert code != 0
    assert "stale" in str(result).lower() or "digest" in str(result).lower()


def test_gate_close_g4_succeeds_on_empty_findings_and_true_predicates(
    tmp_path: Path,
) -> None:
    _drive_to_g4(tmp_path)
    code, recorded = _record_ok_recompose_report(tmp_path)
    assert code == 0, recorded
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G4")
    assert code == 0, result
    assert result.get("closed") == "G4"
    assert result.get("active_gate") == "complete"
    code, ctx = _run_gate(tmp_path, "resolve-context")
    assert code == 0, ctx
    assert ctx.get("active_gate") == "complete"
    dqi_path = tmp_path / "inductive-dqi.json"
    if dqi_path.is_file():
        dqi = json.loads(dqi_path.read_text(encoding="utf-8"))
        assert "recompose_check" not in dqi


def test_gate_close_g4_fails_when_findings_remain_or_predicate_false(
    tmp_path: Path,
) -> None:
    _drive_to_g4(tmp_path)
    code, recorded = _record_ok_recompose_report(
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
    assert code == 0, recorded
    code, result = _run_gate(tmp_path, "gate-close", "--gate", "G4")
    assert code != 0
    assert "finding" in str(result).lower() or "buildable" in str(result).lower()


def test_g4_facade_check_and_list_speak_findings_and_digests(tmp_path: Path) -> None:
    _drive_to_g4(tmp_path)
    facts_digest, opens_digest = _current_digests(tmp_path)
    code, recorded = _record_ok_recompose_report(tmp_path)
    assert code == 0, recorded
    code, result = _run_gate(tmp_path, "g4-check-report")
    assert code == 0, result
    assert result.get("closable") is True
    assert result.get("findings") == []
    assert result.get("facts_digest") == facts_digest
    assert result.get("opens_digest") == opens_digest

    code, listed = _run_gate(tmp_path, "g4-list-report")
    assert code == 0, listed
    assert listed.get("buildable") is True
    assert listed.get("findings") == []
    assert listed.get("facts_digest") == facts_digest
