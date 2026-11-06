#!/usr/bin/env python3
"""Topic Approach's Ticket graph is a distinct Decision dimension."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from dec_domain_constraints_schema import (  # noqa: E402
    ALL_X_DIMENSIONS,
    default_kernel_constraints,
    load_constraints_config,
)
from dec_gate_control import cmd_gate_close, cmd_init_session, cmd_resolve_context  # noqa: E402
from dec_test_helpers import load_gate_payload_file, load_rendered_doc  # noqa: E402
from test_dec_gate_loop_a import _full_template  # noqa: E402

_ROOT = Path(__file__).resolve().parents[3]
_TOPIC = _ROOT / "lulu-approach" / "constraints-topic.json"
_DIMENSION = "ticket_dependency_graph"
_EXPECTED_PROFILE = {
    "goal": "Make the work needed to realize the architecture direction clear and ready for follow-on work.",
    "question": "What work must be done to realize this architecture direction, and how do these work items depend on and connect to one another?",
    "completion": "Complete when all work required to complete the Topic is covered by Tickets with no omissions; what each Ticket covers and its boundaries are clear; and the dependencies between Tickets are clear and acyclic.",
}


def test_ticket_dimension_is_topic_approach_only() -> None:
    topic = load_constraints_config(_TOPIC)
    assert set(topic["x_dimensions"]) == {*ALL_X_DIMENSIONS, _DIMENSION}
    assert topic["domain"]["dimension_profile"][_DIMENSION] == _EXPECTED_PROFILE
    for holder in ("lulu-approach/constraints-feature.json", "lulu-bet/constraints-topic.json", "lulu-bet/constraints-feature.json"):
        other = load_constraints_config(_ROOT / holder)
        assert _DIMENSION not in other["x_dimensions"]
        assert _DIMENSION not in other["domain"]["dimension_profile"]
    assert _DIMENSION not in default_kernel_constraints(stage="decision")["x_dimensions"]


def test_topic_ticket_graph_crosses_decision_gates_and_reaches_doc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    config_dir = tmp_path / ".cursor" / "lulu-workflow"
    config_dir.mkdir(parents=True)
    template = tmp_path / "decision-doc.template.md"
    template.write_text(_full_template(), encoding="utf-8")
    (config_dir / "workflow-config.json").write_text(
        json.dumps({"decision": {"decision_doc_template_url": template.as_uri()}}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    cycle, stage = "topic-ticket-graph", "lulu-approach"
    assert cmd_init_session(tmp_path, cycle, stage, constraints_path=_TOPIC) == 0
    capsys.readouterr()
    assert cmd_resolve_context(tmp_path, cycle, stage, constraints_path=_TOPIC) == 0
    ctx = json.loads(capsys.readouterr().out)["domain_constraints"]
    assert _DIMENSION in ctx["x_dimensions"]
    assert ctx["domain"]["dimension_profile"][_DIMENSION] == _EXPECTED_PROFILE

    assert cmd_gate_close(tmp_path, cycle, stage, "O", {"user_confirmed": True}) == 0
    assert cmd_gate_close(tmp_path, cycle, stage, "Q", {"problem_statement": "problem", "constraints": "none"}) == 0
    exchanges = [
        {"lens": dimension, "question": "What matters?", "answer": "The outcome", "na": False}
        for dimension in ctx["x_dimensions"]
    ]
    assert cmd_gate_close(tmp_path, cycle, stage, "GL", {
        "exchanges": [row for row in exchanges if row["lens"] != _DIMENSION], "user_confirmed": True,
    }) != 0
    assert cmd_gate_close(tmp_path, cycle, stage, "GL", {"exchanges": exchanges, "user_confirmed": True}) == 0
    assert cmd_gate_close(tmp_path, cycle, stage, "E", {
        "directions": [
            {"name": "A", "approach": "a", "pros": "p", "cons": "c", "recommended": True},
            {"name": "B", "approach": "b", "pros": "p", "cons": "c"},
        ], "excluded": [], "user_choice": "A",
    }) == 0
    assert cmd_gate_close(tmp_path, cycle, stage, "D", {
        "decision_rationale": "r", "applies_to": "scope", "excludes": "none", "execution_approach": "serial",
    }) == 0
    x_payload = {
        "acceptance_criteria": "Outcome is achieved", "gap": "None", "impact_surface": [],
        "external_dependencies": [], "key_changes": "Implement direction",
        "critical_constraints": "Existing clients continue working", "reversibility": "partial",
    }
    assert cmd_gate_close(tmp_path, cycle, stage, "X", x_payload) != 0
    graph = (
        "- T1: Define the contract; boundary: public interface.\n"
        "- T2: Implement the service; boundary: server behavior; depends on T1.\n"
        "- T3: Connect the client; boundary: client integration; depends on T2."
    )
    x_payload["dimension_results"] = {_DIMENSION: graph}
    assert cmd_gate_close(tmp_path, cycle, stage, "X", x_payload) == 0
    assert load_gate_payload_file(tmp_path, cycle, "X", stage)["dimension_results"][_DIMENSION] == graph
    doc = load_rendered_doc(tmp_path, cycle, stage)
    assert "Ticket Dependency Graph" in doc
    assert graph in doc
