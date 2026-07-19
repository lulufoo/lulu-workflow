#!/usr/bin/env python3
"""Tests for decision-fact.json schema (cast + id stability)."""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from dec_decision_fact_schema import (  # noqa: E402
    audit_decision_fact_alignment,
    build_decision_fact,
    export_decision_fact,
    load_decision_fact,
    validate_decision_fact,
)
from dec_gate_payload_schema import save_gate_payload  # noqa: E402


def _sample_payloads() -> dict:
    return {
        "Q": {
            "problem_statement": "need micro-routing",
            "constraints": "no full-page nav",
        },
        "GL": {
            "exchanges": [
                {
                    "topic": "T1",
                    "question": "Who confirms?",
                    "answer": "Owner",
                    "na": False,
                },
                {
                    "topic": "T2",
                    "question": "Human vs machine?",
                    "answer": "Human",
                    "na": False,
                },
                {
                    "topic": "T3",
                    "question": "Risk?",
                    "answer": "Latency",
                    "na": False,
                },
                {
                    "topic": "T4",
                    "question": "Ops?",
                    "answer": "Business hours",
                    "na": False,
                },
            ],
            "user_confirmed": True,
        },
        "E": {
            "directions": [
                {
                    "name": "A",
                    "approach": "hash",
                    "pros": "simple",
                    "cons": "limited",
                    "recommended": True,
                },
                {"name": "B", "approach": "history", "pros": "native", "cons": "complex"},
            ],
            "excluded": [{"name": "C", "reason": "too heavy"}],
            "user_choice": "A",
        },
        "D": {
            "decision_rationale": "pick A",
            "applies_to": "list↔note",
            "excludes": "full-page",
            "execution_approach": "phase 1 then 2",
        },
        "X": {
            "acceptance_criteria": "back works",
            "gap": "None",
            "impact_surface": [
                {
                    "layer": "ui",
                    "area": "router",
                    "change_type": "add",
                    "notes": "hash listener",
                }
            ],
            "external_dependencies": [],
            "key_changes": "add listener",
            "critical_constraints": "no Dialog",
            "reversibility": "easy",
        },
        "R": {"exit": "dc"},
        "DC": {"user_confirmed": True},
    }


def _sample_registers() -> dict:
    return {
        "version": "1",
        "cycle_id": "c1",
        "stage": "decision",
        "prior": [
            {
                "id": "P1",
                "kind": "preference",
                "state": "pending",
                "source": "O",
                "text": "prefer lightweight",
            }
        ],
        "assumptions": [
            {
                "id": "A1",
                "state": "pending",
                "source": "R",
                "text": "history API available",
            }
        ],
        "next_prior_seq": 2,
        "next_assumption_seq": 2,
        "updated_at": "2026-07-19T00:00:00+00:00",
    }


def test_build_casts_text_and_list_fields() -> None:
    fact = build_decision_fact(_sample_payloads(), registers=_sample_registers())
    assert fact["version"] == 1
    assert "Q" in fact["gates"]
    assert "GL" in fact["gates"]
    assert "E" in fact["gates"]
    assert "D" in fact["gates"]
    assert "X" in fact["gates"]
    assert "R" in fact["gates"]
    assert "user_prior" in fact["gates"]
    assert "assumptions" in fact["gates"]
    # Control-only gates are not cast.
    assert "DC" not in fact["gates"]

    q_texts = {u["text"] for u in fact["gates"]["Q"]}
    assert "need micro-routing" in q_texts
    assert "no full-page nav" in q_texts

    gl_slots = {u["slot"] for u in fact["gates"]["GL"]}
    assert "GL.exchanges[topic=T1]" in gl_slots
    assert any("topic: T3" in u["text"] for u in fact["gates"]["GL"])

    e_ids = [u["id"] for u in fact["gates"]["E"]]
    assert e_ids[0].startswith("E-")
    assert any("name: A" in u["text"] for u in fact["gates"]["E"])
    assert any(u["text"] == "A" for u in fact["gates"]["E"])  # user_choice

    d_slots = {u["slot"] for u in fact["gates"]["D"]}
    assert d_slots == {
        "D.decision_rationale",
        "D.applies_to",
        "D.excludes",
        "D.execution_approach",
    }

    assert fact["gates"]["user_prior"][0]["id"] == "P1"
    assert fact["gates"]["assumptions"][0]["id"] == "A1"
    assert validate_decision_fact(fact) == []


def test_skips_empty_text_fields() -> None:
    payloads = {
        "D": {
            "decision_rationale": "keep",
            "applies_to": "x",
            "excludes": "y",
            "execution_approach": "z",
        },
        "R": {"exit": "dc", "realign_gate": "   "},
    }
    fact = build_decision_fact(payloads)
    r_slots = {u["slot"] for u in fact["gates"]["R"]}
    assert r_slots == {"R.exit"}


def test_register_without_id_uses_content_stable_slot() -> None:
    """Missing register id must not use list index (reorder would steal ids)."""
    registers = {
        "version": "1",
        "cycle_id": "c1",
        "stage": "decision",
        "prior": [
            {"kind": "preference", "state": "pending", "source": "O", "text": "alpha prior"},
            {"kind": "preference", "state": "pending", "source": "O", "text": "beta prior"},
        ],
        "assumptions": [],
        "next_prior_seq": 1,
        "next_assumption_seq": 1,
        "updated_at": "2026-07-19T00:00:00+00:00",
    }
    first = build_decision_fact({"D": {"decision_rationale": "x", "applies_to": "a", "excludes": "b", "execution_approach": "c"}}, registers=registers)
    first_by_text = {u["text"]: (u["id"], u["slot"]) for u in first["gates"]["user_prior"]}
    assert all("sha256=" in slot for _, slot in first_by_text.values())

    registers["prior"] = list(reversed(registers["prior"]))
    second = build_decision_fact(
        {"D": {"decision_rationale": "x", "applies_to": "a", "excludes": "b", "execution_approach": "c"}},
        registers=registers,
        previous=first,
    )
    second_by_text = {u["text"]: (u["id"], u["slot"]) for u in second["gates"]["user_prior"]}
    assert first_by_text["alpha prior"][0] == second_by_text["alpha prior"][0]
    assert first_by_text["beta prior"][0] == second_by_text["beta prior"][0]
    assert first_by_text["alpha prior"][1] == second_by_text["alpha prior"][1]


def test_reexport_preserves_ids_by_slot() -> None:
    first = build_decision_fact(_sample_payloads(), registers=_sample_registers())
    # Mutate texts but keep slots; add a new direction.
    payloads = _sample_payloads()
    payloads["D"]["decision_rationale"] = "pick A (revised)"
    payloads["E"]["directions"].append(
        {"name": "D", "approach": "hybrid", "pros": "p", "cons": "c"}
    )
    second = build_decision_fact(payloads, registers=_sample_registers(), previous=first)

    first_by_slot = {u["slot"]: u["id"] for u in first["gates"]["D"]}
    second_by_slot = {u["slot"]: u["id"] for u in second["gates"]["D"]}
    assert first_by_slot == second_by_slot

    first_e = {u["slot"]: u["id"] for u in first["gates"]["E"]}
    second_e = {u["slot"]: u["id"] for u in second["gates"]["E"]}
    for slot, unit_id in first_e.items():
        assert second_e[slot] == unit_id
    # New direction gets a fresh id that does not collide.
    new_slots = set(second_e) - set(first_e)
    assert len(new_slots) == 1
    new_id = second_e[next(iter(new_slots))]
    assert new_id not in first_e.values()


def test_reexport_preserves_ids_on_list_insert() -> None:
    """Insert at front must not steal the trailing item's unit id (index rematch bug)."""
    first = build_decision_fact(_sample_payloads())
    by_name = {
        u["slot"]: (u["id"], u["text"])
        for u in first["gates"]["E"]
        if u["slot"].startswith("E.directions[")
    }
    slot_a = "E.directions[name=A]"
    slot_b = "E.directions[name=B]"
    assert slot_a in by_name and slot_b in by_name
    id_a, text_a = by_name[slot_a]
    id_b, text_b = by_name[slot_b]

    payloads = _sample_payloads()
    payloads["E"]["directions"].insert(
        0,
        {"name": "Z", "approach": "new", "pros": "p", "cons": "c"},
    )
    second = build_decision_fact(payloads, previous=first)
    second_by_slot = {u["slot"]: u for u in second["gates"]["E"]}
    assert second_by_slot[slot_a]["id"] == id_a
    assert "name: A" in second_by_slot[slot_a]["text"]
    assert text_a in second_by_slot[slot_a]["text"] or "name: A" in second_by_slot[slot_a]["text"]
    assert second_by_slot[slot_b]["id"] == id_b
    assert "name: B" in second_by_slot[slot_b]["text"]
    assert second_by_slot[slot_a]["text"] != text_b  # A must not carry B's identity
    assert "E.directions[name=Z]" in second_by_slot
    assert second_by_slot["E.directions[name=Z]"]["id"] not in {id_a, id_b}


def test_export_roundtrip(tmp_path: Path) -> None:
    payloads_dir = tmp_path / "gate-payloads"
    payloads_dir.mkdir()
    for gate, payload in _sample_payloads().items():
        save_gate_payload(payloads_dir / f"{gate}.json", payload)

    out = tmp_path / "decision-fact.json"
    export_decision_fact(payloads_dir, out, registers=_sample_registers())
    loaded = load_decision_fact(out)
    assert loaded["gates"]["D"][0]["text"] == "pick A"

    # Re-export with text change keeps D.decision_rationale id.
    payloads = _sample_payloads()
    payloads["D"]["decision_rationale"] = "pick A v2"
    save_gate_payload(payloads_dir / "D.json", payloads["D"])
    before = {u["slot"]: u["id"] for u in loaded["gates"]["D"]}
    export_decision_fact(payloads_dir, out, registers=_sample_registers())
    after = load_decision_fact(out)
    after_ids = {u["slot"]: u["id"] for u in after["gates"]["D"]}
    assert before == after_ids
    rationale = next(u for u in after["gates"]["D"] if u["slot"] == "D.decision_rationale")
    assert rationale["text"] == "pick A v2"


def test_validate_flags_missing_fields() -> None:
    bad = {
        "version": 1,
        "gates": {
            "D": [{"id": "", "text": "x"}, {"id": "D-1", "text": ""}],
        },
    }
    errors = validate_decision_fact(bad)
    assert any("id is required" in e for e in errors)
    assert any("text is required" in e for e in errors)


def test_validate_flags_duplicate_ids() -> None:
    bad = {
        "version": 1,
        "gates": {
            "D": [
                {"id": "D-1", "text": "a"},
                {"id": "D-1", "text": "b"},
            ],
        },
    }
    errors = validate_decision_fact(bad)
    assert any("duplicate" in e for e in errors)


def test_audit_passes_when_aligned() -> None:
    payloads = _sample_payloads()
    registers = _sample_registers()
    fact = build_decision_fact(payloads, registers=registers)
    assert audit_decision_fact_alignment(fact, payloads, registers=registers) == []


def test_audit_flags_text_drift() -> None:
    payloads = _sample_payloads()
    registers = _sample_registers()
    fact = build_decision_fact(payloads, registers=registers)
    drifted = _sample_payloads()
    drifted["D"]["decision_rationale"] = "changed without re-export"
    errors = audit_decision_fact_alignment(fact, drifted, registers=registers)
    assert any("text drift" in e and "D.decision_rationale" in e for e in errors)


def test_audit_flags_orphan_and_missing_slots() -> None:
    payloads = _sample_payloads()
    fact = build_decision_fact(payloads)
    fact["gates"]["D"].append({"id": "D-99", "slot": "D.ghost", "text": "orphan"})
    fact["gates"]["D"] = [u for u in fact["gates"]["D"] if u["slot"] != "D.excludes"]
    errors = audit_decision_fact_alignment(fact, payloads)
    assert any("orphan unit slot" in e and "D.ghost" in e for e in errors)
    assert any("missing unit" in e and "D.excludes" in e for e in errors)
