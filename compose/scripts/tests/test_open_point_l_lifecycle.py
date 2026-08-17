#!/usr/bin/env python3
"""L lifecycle guards and atomic G3 --from-report transaction."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bootstrap  # noqa: F401
import pytest

import l_step_control
from l_ledger_schema import build_ledger, load_l_ledger, save_l_ledger
from l_shell_control import cmd_advance
from scope_package_schema import build_scope_package, save_scope_package, write_source_path_mirrors
from session_state_schema import load_active_doc, resolve_path
from workflow_paths import seed_profile_pointer_for_tests
from workflow_profile_paths import state_path
from workflow_state_schema import init_compose_session, save_workflow_state

_INDUCTIVE_DIR = Path(__file__).resolve().parent.parent / "inductive"
_SCHEMA_DIR = _INDUCTIVE_DIR / "schema"
sys.path.insert(0, str(_INDUCTIVE_DIR))
sys.path.insert(0, str(_SCHEMA_DIR))

import open_point_store  # noqa: E402
from compose_state_lock import canonical_digest  # noqa: E402
from g4_recompose_report_schema import g4_report_path, save_report  # noqa: E402
from inductive_gate_control import _reopen_g3_from_report, cmd_gate_close  # noqa: E402
from inductive_gate_state_schema import (  # noqa: E402
    close_gate,
    init_gate_state,
    load_gate_state,
    save_gate_state,
)
from open_point_store import (  # noqa: E402
    add_opens,
    load_bundle,
    reconcile,
    settle_open,
)
from open_point_transaction_schema import open_point_txn_path  # noqa: E402
from opens_schema import load_opens, opens_path  # noqa: E402

_CYCLE = "feat-op-l"
_PROFILE = "lulu-design"


def _human_open(**overrides):
    item = {
        "question": "What breaks first?",
        "basis": "Intent and facts collide on the write path",
        "blocking": True,
        "source": {"actor": "human", "means": "direct"},
        "lens": "I",
    }
    item.update(overrides)
    return item


def _finding():
    return {
        "question": "Who owns retry?",
        "basis": "Two facts disagree on ownership",
        "blocking": True,
        "lens": "I",
    }


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _g4_closed_state(out_dir: Path) -> dict:
    state = init_gate_state(cycle_id="c1", stage="lulu-design")
    for gate in ("G1", "G2", "G3"):
        state = close_gate(state, gate)
    save_gate_state(out_dir / "inductive-gate-state.json", state)
    return load_gate_state(out_dir / "inductive-gate-state.json")


def _finding_report(out_dir: Path) -> tuple[dict, str]:
    facts = [{"id": "F-seed", "text": "g4 lens source", "lens_tags": ["I"]}]
    (out_dir / "_facts.json").write_text(
        json.dumps(facts) + "\n", encoding="utf-8"
    )
    facts_d = canonical_digest(facts)
    opens_d = canonical_digest(load_opens(opens_path(out_dir)))
    report = {
        "version": 1,
        "facts_digest": facts_d,
        "opens_digest": opens_d,
        "findings": [_finding()],
        "buildable": False,
        "reversible": True,
        "verifiable": True,
        "evidence": {
            "buildable": "ownership is split",
            "reversible": "retry can be unwound",
            "verifiable": "owner is observable",
        },
        "produced_by": "subagent",
    }
    saved = save_report(g4_report_path(out_dir), report)
    return saved, canonical_digest(saved)


def _from_report_args(digest: str) -> argparse.Namespace:
    return argparse.Namespace(
        gate="G3",
        from_report=True,
        report_digest=digest,
        sections="",
    )


def _seed_ledger(rev: Path, *, order: list[str] | None = None) -> dict:
    ledger = build_ledger(order or ["L1", "L2"])
    save_l_ledger(rev, ledger)
    for nid in ledger["order"]:
        (rev / nid).mkdir(parents=True, exist_ok=True)
    return load_l_ledger(rev)


def _seed_inductive_session(tmp_path: Path, *, order: list[str] | None = None) -> Path:
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, _PROFILE)
    active_doc = load_active_doc(resolve_path(_CYCLE, tmp_path, _PROFILE))
    ws = tmp_path / state_path(_CYCLE, active_doc, _PROFILE, tmp_path)
    init_compose_session(ws, mode="tech", cycle_type="feature")
    save_workflow_state(ws, {"current_state": "Working"})
    rev = ws.parent
    ids = order or ["L1", "L2"]
    save_l_ledger(rev, build_ledger(ids))
    src = tmp_path / "scope-src.md"
    src.write_text("# scope\n", encoding="utf-8")
    package = build_scope_package(
        [{"id": nid, "title": nid, "source_path": str(src.resolve())} for nid in ids]
    )
    save_scope_package(rev, package)
    write_source_path_mirrors(rev, package)
    return ws


def _set_cell(rev: Path, nid: str, *, state: str | None = None, frozen: bool | None = None) -> None:
    ledger = load_l_ledger(rev)
    if state is not None:
        ledger["by_id"][nid]["state"] = state
    if frozen is not None:
        ledger["by_id"][nid]["frozen"] = frozen
    save_l_ledger(rev, ledger)


def _set_focus(rev: Path, nid: str) -> None:
    ledger = load_l_ledger(rev)
    ledger["focus"] = nid
    save_l_ledger(rev, ledger)


def _repair_required_txn(slice_dir: Path) -> None:
    before = [
        {
            "id": "O-1",
            "status": "open",
            "source": {"actor": "human", "means": "direct"},
            "question": "q",
            "basis": "b",
            "blocking": False,
        }
    ]
    _write_json(opens_path(slice_dir), [{"id": "O-99"}])
    _write_json(
        open_point_txn_path(slice_dir),
        {
            "version": 1,
            "operation": "add-opens",
            "targets": {
                "inductive-opens.json": {
                    "existed": True,
                    "before": before,
                    "after_digest": canonical_digest([]),
                }
            },
        },
    )


def _close_producer_gates(slice_dir: Path) -> None:
    state = init_gate_state(cycle_id="c1", stage="lulu-design")
    for gate in ("G1", "G2", "G3", "G4"):
        state = close_gate(state, gate)
    save_gate_state(slice_dir / "inductive-gate-state.json", state)


def test_from_report_crash_after_opens_restores_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    state = _g4_closed_state(tmp_path)
    _, digest = _finding_report(tmp_path)
    before_opens = load_opens(opens_path(tmp_path))
    before_gate = load_gate_state(tmp_path / "inductive-gate-state.json")
    report_path = g4_report_path(tmp_path)
    assert report_path.is_file()

    original = open_point_store.durable_write_json
    crashed = {"done": False}

    def crash_on_gate(path, value):
        if Path(path).name == "inductive-gate-state.json" and not crashed["done"]:
            crashed["done"] = True
            raise RuntimeError("injected crash")
        return original(path, value)

    monkeypatch.setattr(open_point_store, "durable_write_json", crash_on_gate)
    with pytest.raises(RuntimeError, match="injected crash"):
        _reopen_g3_from_report(tmp_path, _from_report_args(digest), state)

    reconcile(tmp_path)
    assert load_opens(opens_path(tmp_path)) == before_opens
    gate = load_gate_state(tmp_path / "inductive-gate-state.json")
    assert gate["active_gate"] == before_gate["active_gate"]
    assert gate["gates"]["G3"]["status"] == "closed"
    assert report_path.is_file()
    assert not open_point_txn_path(tmp_path).is_file()


def test_from_report_success_deletes_report_and_reopens_g3(tmp_path: Path):
    state = _g4_closed_state(tmp_path)
    _, digest = _finding_report(tmp_path)
    _reopen_g3_from_report(tmp_path, _from_report_args(digest), state)
    gate = load_gate_state(tmp_path / "inductive-gate-state.json")
    assert gate["active_gate"] == "G3"
    assert gate["gates"]["G3"]["status"] == "reopened"
    assert gate["gates"]["G4"]["status"] == "pending"
    assert not g4_report_path(tmp_path).exists()
    opens = load_opens(opens_path(tmp_path))
    assert len(opens) == 1
    assert opens[0]["question"] == "Who owns retry?"
    assert opens[0]["source"] == {"actor": "ai", "means": "audit"}
    assert not open_point_txn_path(tmp_path).is_file()


def test_add_opens_refused_on_frozen_slice(tmp_path: Path):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_ledger(rev)
    _set_cell(rev, "L2", frozen=True)
    with pytest.raises(Exception, match="frozen"):
        add_opens(rev / "L2", opens=[_human_open()])


def test_settle_refused_on_frozen_slice(tmp_path: Path):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_ledger(rev)
    _set_cell(rev, "L1", state="Completed")
    _set_focus(rev, "L2")
    add_opens(rev / "L2", opens=[_human_open()])
    _set_focus(rev, "L1")
    _set_cell(rev, "L2", frozen=True)
    with pytest.raises(Exception, match="frozen"):
        settle_open(rev / "L2", "O-1", ["F-1"])


def test_gate_close_g3_refused_on_frozen_slice(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_ledger(rev)
    _set_cell(rev, "L2", frozen=True)
    slice_dir = rev / "L2"
    state = init_gate_state(cycle_id="c1", stage="lulu-design")
    state = close_gate(state, "G1")
    state = close_gate(state, "G2")
    save_gate_state(slice_dir / "inductive-gate-state.json", state)
    args = argparse.Namespace(gate="G3", mode="cleared", confirm=True, payload=None)
    with pytest.raises(SystemExit):
        cmd_gate_close(slice_dir, args)
    captured = capsys.readouterr().out.lower()
    assert "frozen" in captured
    gate = load_gate_state(slice_dir / "inductive-gate-state.json")
    assert gate["active_gate"] == "G3"
    assert gate["gates"]["G3"]["status"] != "closed"


def test_add_opens_refused_when_slice_is_not_focus(tmp_path: Path):
    rev = tmp_path / "rev"
    rev.mkdir()
    _seed_ledger(rev)
    _set_cell(rev, "L1", state="Completed")
    _set_focus(rev, "L2")
    with pytest.raises(Exception, match="focus"):
        add_opens(rev / "L1", opens=[_human_open()])


def test_enter_inductive_l2_does_not_copy_l1_open_point(tmp_path: Path):
    ws = _seed_inductive_session(tmp_path, order=["L1", "L2"])
    rev = ws.parent
    l1 = rev / "L1"
    l1.mkdir(parents=True, exist_ok=True)
    add_opens(l1, opens=[_human_open(question="L1 only")])
    _write_json(
        l1 / "open-point-detect-receipts.json",
        {
            "version": 1,
            "receipts": [
                {
                    "id": "R-1",
                    "checked_lenses": ["I"],
                    "facts_digest": canonical_digest([]),
                    "lens_digest": canonical_digest([]),
                    "opens_digest": canonical_digest([]),
                    "raw_candidate_count": 1,
                    "raw_candidate_digest": canonical_digest([_finding()]),
                    "final_open_ids": ["O-1"],
                    "zero_result": False,
                }
            ],
        },
    )
    state = init_gate_state(cycle_id=_CYCLE, stage=_PROFILE)
    for gate in ("G1", "G2", "G3"):
        state = close_gate(state, gate)
    save_gate_state(l1 / "inductive-gate-state.json", state)
    l1_opens = load_opens(opens_path(l1))
    l1_receipts = json.loads((l1 / "open-point-detect-receipts.json").read_text(encoding="utf-8"))
    l1_gate = load_gate_state(l1 / "inductive-gate-state.json")

    _set_cell(rev, "L1", state="Completed")
    _set_focus(rev, "L2")
    _set_cell(rev, "L2", state="FactIntake")
    l2_dir = rev / "L2"
    l2_dir.mkdir(parents=True, exist_ok=True)
    (l2_dir / "_fact_intake.complete").write_text("ok\n", encoding="utf-8")
    result = l_step_control.enter_inductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is True, result
    l2 = rev / "L2"
    bundle = load_bundle(l2)
    assert bundle["opens"] == []
    assert bundle["state"]["phase"] == "idle"
    assert bundle["batches"]["batches"] == []
    assert bundle["receipts"]["receipts"] == []
    assert (l2 / "inductive-opens.json").is_file()
    assert (l2 / "open-point-state.json").is_file()
    assert (l2 / "open-point-batches.json").is_file()
    assert (l2 / "open-point-detect-receipts.json").is_file()
    gate = load_gate_state(l2 / "inductive-gate-state.json")
    assert gate["active_gate"] == "G1"
    assert gate["gates"]["G1"]["status"] == "active"
    assert load_opens(opens_path(l1)) == l1_opens
    assert json.loads((l1 / "open-point-detect-receipts.json").read_text(encoding="utf-8")) == l1_receipts
    assert load_gate_state(l1 / "inductive-gate-state.json")["active_gate"] == l1_gate["active_gate"]


def test_complete_inductive_fails_while_txn_repair_required(tmp_path: Path):
    ws = _seed_inductive_session(tmp_path, order=["L1"])
    rev = ws.parent
    _set_cell(rev, "L1", state="Inductive")
    l1 = rev / "L1"
    (l1 / "_facts.json").write_text("[]\n", encoding="utf-8")
    _close_producer_gates(l1)
    _repair_required_txn(l1)
    result = l_step_control.complete_inductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    blob = str(result).lower()
    assert "repair" in blob or "txn" in blob or "transaction" in blob
    assert open_point_txn_path(l1).is_file()


def test_advance_fails_while_txn_repair_required(tmp_path: Path):
    ledger = build_ledger(["L1", "L2"])
    ledger["by_id"]["L1"]["state"] = "Completed"
    save_l_ledger(tmp_path, ledger)
    l1 = tmp_path / "L1"
    l1.mkdir(parents=True, exist_ok=True)
    _repair_required_txn(l1)
    payload = cmd_advance(tmp_path, "Working")
    assert payload["ok"] is False
    blob = str(payload).lower()
    assert "repair" in blob or "txn" in blob or "transaction" in blob
    assert load_l_ledger(tmp_path)["focus"] == "L1"
    assert open_point_txn_path(l1).is_file()


def test_complete_inductive_still_requires_g4_complete(tmp_path: Path):
    ws = _seed_inductive_session(tmp_path, order=["L1"])
    rev = ws.parent
    _set_cell(rev, "L1", state="Inductive")
    l1 = rev / "L1"
    (l1 / "_facts.json").write_text("[]\n", encoding="utf-8")
    result = l_step_control.complete_inductive(_CYCLE, tmp_path, profile_id=_PROFILE)
    assert result["ok"] is False
    assert result["code"] == "inductive_incomplete"
