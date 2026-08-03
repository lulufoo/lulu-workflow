#!/usr/bin/env python3
"""Tests for decision-eval-target bind/render."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from dec_domain_constraints_schema import normalize_domain_constraints  # noqa: E402
from dec_eval_target_schema import (  # noqa: E402
    render_and_save_eval_target,
    render_eval_target,
    validate_eval_target_inputs,
)
from dec_gate_payload_schema import save_gate_payload  # noqa: E402
from dec_register_schema import init_registers, save_registers  # noqa: E402


def _constraints() -> dict:
    return normalize_domain_constraints(
        {
            "version": "1",
            "stage": "decision",
            "cache_subdir": "decision",
        }
    )


def test_validate_requires_gate_payloads() -> None:
    errors = validate_eval_target_inputs(
        payloads={},
        registers=init_registers(cycle_id="c1", stage="decision"),
        constraints=_constraints(),
    )
    assert any("Q.json" in err for err in errors)


def test_render_eval_target_formal_fields(tmp_path: Path) -> None:
    session = tmp_path / "decision"
    payloads_dir = session / "gate-payloads"
    payloads_dir.mkdir(parents=True)
    save_gate_payload(
        payloads_dir / "Q.json",
        {"problem_statement": "P", "constraints": "C"},
    )
    save_gate_payload(
        payloads_dir / "E.json",
        {
            "directions": [{"name": "A", "approach": "a", "pros": "p", "cons": "c"}],
            "excluded": [],
            "user_choice": "A",
        },
    )
    save_gate_payload(
        payloads_dir / "D.json",
        {
            "decision_rationale": "why A",
            "applies_to": "scope",
            "excludes": "out",
            "execution_approach": "phase 1",
        },
    )
    save_gate_payload(
        payloads_dir / "X.json",
        {
            "acceptance_criteria": "ac",
            "gap": "None",
            "impact_surface": [],
            "external_dependencies": [],
            "key_changes": "k",
            "critical_constraints": "cc",
            "reversibility": "easy",
        },
    )
    save_registers(
        session / "registers.json",
        init_registers(cycle_id="c1", stage="decision"),
        r_gate_closed=False,
    )
    (session / "domain-constraints.json").write_text(
        json.dumps(_constraints()), encoding="utf-8"
    )

    path = render_and_save_eval_target(
        session,
        cycle_id="c1",
        stage="decision",
        constraints=_constraints(),
        r_gate_closed=False,
    )
    text = path.read_text(encoding="utf-8")
    assert "# Decision EvalTarget" in text
    assert "<!-- chapter:problem -->" in text
    assert "<!-- chapter:settled_direction -->" in text
    assert "source: gate-payloads/D.json" in text
    assert "- decision_rationale: why A" in text
    assert "- user_choice: A" in text
    assert "<!-- chapter:assumptions -->" in text


def test_render_rejects_missing_payload() -> None:
    with pytest.raises(ValueError, match="missing gate payload"):
        render_eval_target(
            cycle_id="c1",
            stage="decision",
            payloads={"Q": {"problem_statement": "p", "constraints": "c"}},
            registers=init_registers(cycle_id="c1", stage="decision"),
            constraints=_constraints(),
        )
