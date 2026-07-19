#!/usr/bin/env python3
"""Tests for decision-fact claim ledger (Step 3)."""

from __future__ import annotations

import json
from pathlib import Path

import bootstrap  # noqa: F401
from decision_fact_claim_control import cmd_check, cmd_ensure, cmd_set_status  # noqa: E402
import pytest

from decision_fact_claim_schema import (  # noqa: E402
    build_units_ledger,
    claim_ledger_path,
    claim_report,
    ensure_claim_ledger,
    evaluate_claim_gate,
    flatten_unit_ids,
    load_claim_ledger,
)
from resolved_refs_schema import write_resolved_refs  # noqa: E402
from delivered_refs_schema import DeliveredRef  # noqa: E402


def _fact(units_by_gate: dict[str, list[str]]) -> dict:
    gates = {}
    for gate, texts in units_by_gate.items():
        gates[gate] = [
            {"id": f"{gate}-{i + 1}", "slot": f"{gate}.f{i}", "text": t}
            for i, t in enumerate(texts)
        ]
    return {"version": 1, "gates": gates}


def test_flatten_unit_ids_stable() -> None:
    fact = _fact({"D": ["a", "b"], "Q": ["q"]})
    assert flatten_unit_ids(fact) == ["D-1", "D-2", "Q-1"]


def test_ensure_prose_fallback_when_missing(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    write_resolved_refs(
        rev,
        cycle_id="c1",
        stage="lulu-design",
        run_mode="tech",
        scope_ref=DeliveredRef(type="lulu-approach", path="/abs/doc.md"),
        intent_baseline_refs=[],
        norm_constraint_refs=[],
    )
    ledger = ensure_claim_ledger(rev, decision_fact_path=None)
    assert ledger["mode"] == "prose_fallback"
    assert claim_report(ledger)["ok"] is True
    assert cmd_ensure(rev) == 0


def test_ensure_units_and_preserves_status(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    fact_path = tmp_path / "decision-fact.json"
    fact_path.write_text(json.dumps(_fact({"D": ["a", "b"]})), encoding="utf-8")
    write_resolved_refs(
        rev,
        cycle_id="c1",
        stage="lulu-design",
        run_mode="tech",
        scope_ref=DeliveredRef(type="lulu-approach", path=str(fact_path)),
        intent_baseline_refs=[],
        norm_constraint_refs=[],
    )
    first = ensure_claim_ledger(rev, decision_fact_path=str(fact_path))
    assert first["mode"] == "units"
    assert set(first["units"]) == {"D-1", "D-2"}
    assert all(u["status"] == "unclaimed" for u in first["units"].values())

    first["units"]["D-1"]["status"] = "settled"
    claim_ledger_path(rev).write_text(
        json.dumps(first, indent=2) + "\n", encoding="utf-8"
    )

    # Drop D-2 from source; add D-3.
    fact_path.write_text(json.dumps(_fact({"D": ["a", "c"]})), encoding="utf-8")
    # Rebuild ids: D-1=a, D-2=c in fresh cast — use explicit ids matching slots.
    fact_path.write_text(
        json.dumps(
            {
                "version": 1,
                "gates": {
                    "D": [
                        {"id": "D-1", "slot": "D.f0", "text": "a"},
                        {"id": "D-3", "slot": "D.f2", "text": "c"},
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    second = ensure_claim_ledger(rev, decision_fact_path=str(fact_path))
    assert second["units"]["D-1"]["status"] == "settled"
    assert second["units"]["D-3"]["status"] == "unclaimed"
    assert "D-2" not in second["units"]
    assert "D-2" in second["orphan_ids"]


def test_check_strict_fails_on_unclaimed(tmp_path: Path, capsys) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    fact_path = tmp_path / "decision-fact.json"
    fact_path.write_text(json.dumps(_fact({"D": ["a"]})), encoding="utf-8")
    write_resolved_refs(
        rev,
        cycle_id="c1",
        stage="lulu-design",
        run_mode="tech",
        scope_ref=DeliveredRef(type="lulu-approach", path=str(fact_path)),
        intent_baseline_refs=[],
        norm_constraint_refs=[],
    )
    assert cmd_check(rev, strict=False) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["unclaimed"] == ["D-1"]
    assert out["orphan_exposed"] == ["D-1"]
    assert out["gate_ok"] is True
    assert cmd_check(rev, strict=True) == 1
    strict_out = json.loads(capsys.readouterr().out)
    assert strict_out["gate_ok"] is False


def test_build_units_ledger_preserves_prior() -> None:
    previous = build_units_ledger(["D-1"], source_ref="/x")
    previous["units"]["D-1"]["status"] = "deferred"
    nxt = build_units_ledger(["D-1", "D-2"], source_ref="/x", previous=previous)
    assert nxt["units"]["D-1"]["status"] == "deferred"
    assert nxt["units"]["D-2"]["status"] == "unclaimed"


def test_save_claim_ledger_atomic_no_tmp_left(tmp_path: Path) -> None:
    from decision_fact_claim_schema import save_claim_ledger  # noqa: E402

    rev = tmp_path / "revision1"
    rev.mkdir()
    ledger = ensure_claim_ledger(rev, decision_fact_path=None)
    path = claim_ledger_path(rev)
    save_claim_ledger(path, ledger)
    assert path.is_file()
    assert not path.with_suffix(path.suffix + ".tmp").exists()
    assert load_claim_ledger(path)["mode"] == "prose_fallback"


def test_ensure_refuses_wipe_when_fact_missing(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    fact_path = tmp_path / "decision-fact.json"
    fact_path.write_text(json.dumps(_fact({"D": ["a"]})), encoding="utf-8")
    ledger = ensure_claim_ledger(rev, decision_fact_path=str(fact_path))
    ledger["units"]["D-1"]["status"] = "settled"
    claim_ledger_path(rev).write_text(
        json.dumps(ledger, indent=2) + "\n", encoding="utf-8"
    )
    fact_path.unlink()
    with pytest.raises(ValueError, match="refusing to wipe"):
        ensure_claim_ledger(rev, decision_fact_path=str(fact_path))
    # Prior settled status must still be on disk.
    assert load_claim_ledger(claim_ledger_path(rev))["units"]["D-1"]["status"] == "settled"


def test_ensure_empty_gates_stays_units_mode(tmp_path: Path) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    fact_path = tmp_path / "decision-fact.json"
    fact_path.write_text(
        json.dumps({"version": 1, "gates": {}}), encoding="utf-8"
    )
    ledger = ensure_claim_ledger(rev, decision_fact_path=str(fact_path))
    assert ledger["mode"] == "units"
    assert ledger["units"] == {}
    assert evaluate_claim_gate(ledger)["gate_ok"] is True


def test_check_fails_on_stale_orphan_ids(tmp_path: Path, capsys) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    fact_path = tmp_path / "decision-fact.json"
    fact_path.write_text(json.dumps(_fact({"D": ["a", "b"]})), encoding="utf-8")
    write_resolved_refs(
        rev,
        cycle_id="c1",
        stage="lulu-design",
        run_mode="tech",
        scope_ref=DeliveredRef(type="lulu-approach", path=str(fact_path)),
        intent_baseline_refs=[],
        norm_constraint_refs=[],
    )
    ensure_claim_ledger(rev, decision_fact_path=str(fact_path))
    cmd_set_status(rev, unit_id="D-1", status="settled", by="seed", note="")
    capsys.readouterr()
    # Shrink source: D-2 disappears → stale orphan fails D6.
    fact_path.write_text(
        json.dumps(
            {
                "version": 1,
                "gates": {
                    "D": [{"id": "D-1", "slot": "D.f0", "text": "a"}],
                },
            }
        ),
        encoding="utf-8",
    )
    assert cmd_check(rev, strict=False) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["gate_ok"] is False
    assert "D-2" in out["stale_orphan_ids"]


def test_evaluate_claim_gate_claimed_open_fails_without_strict() -> None:
    ledger = build_units_ledger(["D-1", "D-2"], source_ref="/x")
    ledger["units"]["D-1"]["status"] = "claimed"
    ledger["units"]["D-2"]["status"] = "unclaimed"
    result = evaluate_claim_gate(ledger, fail_on_unclaimed=False)
    assert result["gate_ok"] is False
    assert result["orphan_exposed"] == ["D-2"]
    assert any("claimed-but-open" in e for e in result["errors"])


def test_set_status_co_batch_claimed_then_settled(tmp_path: Path, capsys) -> None:
    rev = tmp_path / "revision1"
    rev.mkdir()
    fact_path = tmp_path / "decision-fact.json"
    fact_path.write_text(json.dumps(_fact({"D": ["a"]})), encoding="utf-8")
    write_resolved_refs(
        rev,
        cycle_id="c1",
        stage="lulu-design",
        run_mode="tech",
        scope_ref=DeliveredRef(type="lulu-approach", path=str(fact_path)),
        intent_baseline_refs=[],
        norm_constraint_refs=[],
    )
    ensure_claim_ledger(rev, decision_fact_path=str(fact_path))
    assert cmd_set_status(rev, unit_id="D-1", status="claimed", by="seed", note="") == 0
    assert load_claim_ledger(claim_ledger_path(rev))["units"]["D-1"]["status"] == "claimed"
    # D6: claimed-but-open fails even without --strict
    assert cmd_check(rev, strict=False) == 1
    capsys.readouterr()
    assert cmd_set_status(rev, unit_id="D-1", status="settled", by="seed", note="") == 0
    ledger = load_claim_ledger(claim_ledger_path(rev))
    assert ledger["units"]["D-1"]["status"] == "settled"
    assert claim_report(ledger)["settled"] == ["D-1"]
    assert cmd_check(rev, strict=False) == 0
    assert cmd_check(rev, strict=True) == 0
