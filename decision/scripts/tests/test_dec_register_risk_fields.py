"""Schema tests for assumption risk fields (risk_level / risk_state triad)."""

from __future__ import annotations

import pytest

from dec_register_schema import (
    normalize_registers,
    validate_registers,
)


def _base(*, assumptions: list[dict]) -> dict:
    return {
        "version": "1",
        "cycle_id": "c1",
        "stage": "decision",
        "prior": [],
        "assumptions": assumptions,
        "next_prior_seq": 1,
        "next_assumption_seq": len(assumptions) + 1,
    }


def test_assumption_without_state_ok_before_r() -> None:
    data = _base(
        assumptions=[
            {"id": "A1", "source": "O", "text": "claim only"},
        ]
    )
    assert validate_registers(data, r_gate_closed=False) == []


def test_assumption_state_rejected() -> None:
    data = _base(
        assumptions=[
            {"id": "A1", "source": "O", "text": "x", "state": "pending"},
        ]
    )
    errors = validate_registers(data, r_gate_closed=False)
    assert any("state" in e for e in errors)


def test_leftover_assumption_risk_fields_allowed_before_r() -> None:
    data = _base(
        assumptions=[
            {
                "id": "A1",
                "source": "O",
                "text": "x",
                "risk_level": "H",
                "risk_class": "decision",
                "risk_state": "open",
                "risk_consequence": "c",
            }
        ]
    )
    assert validate_registers(data, r_gate_closed=False) == []


def test_triad_none_ok_when_r_closed() -> None:
    data = _base(
        assumptions=[
            {
                "id": "A1",
                "source": "O",
                "text": "x",
                "risk_level": "none",
                "risk_class": "none",
                "risk_state": "none",
                "risk_consequence": "",
            }
        ]
    )
    assert validate_registers(data, r_gate_closed=True) == []


def test_triad_mismatch_rejected() -> None:
    data = _base(
        assumptions=[
            {
                "id": "A1",
                "source": "O",
                "text": "x",
                "risk_level": "none",
                "risk_class": "decision",
                "risk_state": "none",
                "risk_consequence": "c",
            }
        ]
    )
    errors = validate_registers(data, r_gate_closed=True)
    assert any("triad" in e or "none" in e for e in errors)


def test_normalize_migrates_legacy_keys() -> None:
    data = _base(
        assumptions=[
            {
                "id": "A1",
                "source": "O",
                "text": "x",
                "risk": "H",
                "risk_class": "decision",
                "consequence": "boom",
                "verification": "Accepted",
                "disposition": "open",
            }
        ]
    )
    normalized = normalize_registers(data)
    entry = normalized["assumptions"][0]
    assert entry.get("risk_level") == "H"
    assert entry.get("risk_consequence") == "boom"
    assert entry.get("release_terms") == "Accepted"
    assert entry.get("risk_state") == "open"
    assert "risk" not in entry
    assert "consequence" not in entry
    assert "verification" not in entry
    assert "disposition" not in entry


def test_normalize_maps_non_risk_class() -> None:
    data = _base(
        assumptions=[
            {
                "id": "A1",
                "source": "O",
                "text": "x",
                "risk_level": "none",
                "risk_class": "non_risk",
                "risk_state": "none",
            }
        ]
    )
    entry = normalize_registers(data)["assumptions"][0]
    assert entry["risk_class"] == "none"


def test_reject_release_tracking_and_released() -> None:
    tracking = _base(
        assumptions=[
            {
                "id": "A1",
                "source": "O",
                "text": "x",
                "risk_level": "H",
                "risk_class": "decision",
                "risk_state": "open",
                "risk_consequence": "c",
                "release_tracking": True,
            }
        ]
    )
    tracking_errors = validate_registers(tracking, r_gate_closed=True)
    assert any("release_tracking" in e for e in tracking_errors)

    released = _base(
        assumptions=[
            {
                "id": "A1",
                "source": "O",
                "text": "x",
                "risk_level": "H",
                "risk_class": "decision",
                "risk_state": "open",
                "risk_consequence": "c",
                "released": True,
            }
        ]
    )
    released_errors = validate_registers(released, r_gate_closed=True)
    assert any("released" in e for e in released_errors)


def test_constraint_and_risk_rows_validate() -> None:
    data = {
        "version": "1",
        "cycle_id": "c1",
        "stage": "decision",
        "prior": [],
        "assumptions": [{"id": "A1", "source": "O", "text": "unverified"}],
        "constraints": [
            {"id": "C1", "text": "SSO required", "revision": 1, "source": "Q"}
        ],
        "risks": [
            {
                "id": "RK1",
                "source_ref": {"kind": "assumption", "id": "A1"},
                "text": "Client may reject",
                "risk_level": "H",
                "risk_class": "decision",
                "risk_state": "open",
                "risk_consequence": "blocked",
            }
        ],
        "next_prior_seq": 1,
        "next_assumption_seq": 2,
        "next_constraint_seq": 2,
        "next_risk_seq": 2,
    }
    assert validate_registers(data, r_gate_closed=False) == []


def test_ignore_is_not_none_triad() -> None:
    data = _base(
        assumptions=[
            {
                "id": "A1",
                "source": "O",
                "text": "x",
                "risk_level": "none",
                "risk_class": "none",
                "risk_state": "ignore",
                "risk_consequence": "—",
            }
        ]
    )
    errors = validate_registers(data, r_gate_closed=True)
    assert any("triad" in e or "none" in e for e in errors)
