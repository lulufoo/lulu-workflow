#!/usr/bin/env python3
"""Integration coverage for configured Decision dimensions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1]
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from dec_domain_constraints_schema import load_constraints_config  # noqa: E402
from dec_gate_control import cmd_gate_close, cmd_init_session, cmd_resolve_context  # noqa: E402
from dec_test_helpers import load_gate_payload_file, load_rendered_doc  # noqa: E402
from test_dec_gate_loop_a import _full_template  # noqa: E402

_ROOT = Path(__file__).resolve().parents[3]
_FEATURE = _ROOT / "lulu-approach" / "constraints-feature.json"
_CUSTOM = "migration_readiness"
_INACTIVE = "retirement_readiness"
_PROFILE = {
    "goal": "Migration readiness is understood.",
    "question": "What migration work is required?",
    "completion": "Complete when the migration work is explicit.",
}


@pytest.fixture
def configured_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    config_dir = tmp_path / ".cursor" / "lulu-workflow"
    config_dir.mkdir(parents=True)
    template = tmp_path / "decision-doc.template.md"
    template.write_text(_full_template(), encoding="utf-8")
    (config_dir / "workflow-config.json").write_text(
        json.dumps({"decision": {"decision_doc_template_url": template.as_uri()}}),
        encoding="utf-8",
    )
    config = json.loads(_FEATURE.read_text(encoding="utf-8"))
    config["stage"] = "decision"
    config["cache_subdir"] = "decision"
    config["x_dimensions"] = ["acceptance_criteria", _CUSTOM]
    config["domain"]["dimension_profile"].update({_CUSTOM: _PROFILE, _INACTIVE: _PROFILE})
    constraints = tmp_path / "constraints.json"
    constraints.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path, constraints


def _exchange(lens: str) -> dict:
    return {"lens": lens, "question": "What matters?", "answer": "The outcome", "na": False}


def test_configured_dimension_crosses_gates_and_renders(
    configured_project: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    project, constraints_path = configured_project
    cycle, stage = "feature-custom-dimension", "decision"
    assert cmd_init_session(project, cycle, stage, constraints_path=constraints_path) == 0
    capsys.readouterr()
    assert cmd_resolve_context(project, cycle, stage, constraints_path=constraints_path) == 0
    resolved = json.loads(capsys.readouterr().out)["domain_constraints"]
    assert resolved["x_dimensions"] == ["acceptance_criteria", _CUSTOM]
    assert resolved["domain"]["dimension_profile"][_CUSTOM] == _PROFILE
    assert _INACTIVE not in resolved["x_dimensions"]

    assert cmd_gate_close(project, cycle, stage, "O", {"user_confirmed": True}) == 0
    assert cmd_gate_close(project, cycle, stage, "Q", {"problem_statement": "problem", "constraints": "none"}) == 0
    missing_custom = {"exchanges": [_exchange("acceptance_criteria")], "user_confirmed": True}
    assert cmd_gate_close(project, cycle, stage, "GL", missing_custom) != 0
    with_inactive = {"exchanges": [_exchange("acceptance_criteria"), _exchange(_CUSTOM), _exchange(_INACTIVE)], "user_confirmed": True}
    assert cmd_gate_close(project, cycle, stage, "GL", with_inactive) != 0
    active = {"exchanges": [_exchange("acceptance_criteria"), _exchange(_CUSTOM)], "user_confirmed": True}
    assert cmd_gate_close(project, cycle, stage, "GL", active) == 0
    assert cmd_gate_close(project, cycle, stage, "E", {
        "directions": [
            {"name": "A", "approach": "a", "pros": "p", "cons": "c", "recommended": True},
            {"name": "B", "approach": "b", "pros": "p", "cons": "c"},
        ], "excluded": [], "user_choice": "A",
    }) == 0
    assert cmd_gate_close(project, cycle, stage, "D", {
        "decision_rationale": "r", "applies_to": "scope", "excludes": "none", "execution_approach": "serial",
    }) == 0

    payload = {"acceptance_criteria": "Export works", "dimension_results": {_CUSTOM: ""}}
    assert cmd_gate_close(project, cycle, stage, "X", payload) != 0
    assert cmd_gate_close(project, cycle, stage, "X", {"acceptance_criteria": "Export works"}) != 0
    result = "- Prepare the migration\n- Verify the new service"
    payload["dimension_results"][_CUSTOM] = result
    assert cmd_gate_close(project, cycle, stage, "X", payload) == 0
    assert load_gate_payload_file(project, cycle, "X", stage)["dimension_results"][_CUSTOM] == result
    doc = load_rendered_doc(project, cycle, stage)
    assert "Prepare the migration" in doc
    assert "Verify the new service" in doc
    assert "Retirement Readiness" not in doc
    assert "Export works" in doc


def test_default_feature_dimensions_remain_unchanged() -> None:
    config = load_constraints_config(_FEATURE)
    assert set(config["x_dimensions"]) == {
        "acceptance_criteria", "impact_surface", "external_dependencies",
        "implementation_sketch", "gap_check",
    }
    assert _CUSTOM not in config["x_dimensions"]


def test_custom_dimension_cannot_omit_execution_analysis(
    configured_project: tuple[Path, Path],
) -> None:
    _, constraints_path = configured_project
    config = json.loads(constraints_path.read_text(encoding="utf-8"))
    config["omitted_sections"] = ["execution_analysis"]
    constraints_path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="execution_analysis"):
        load_constraints_config(constraints_path)


def test_eval_target_includes_only_active_dimension_results(
    configured_project: tuple[Path, Path],
) -> None:
    from dec_eval_target_schema import render_eval_target
    from dec_register_schema import init_registers

    _, constraints_path = configured_project
    constraints = load_constraints_config(constraints_path)
    target = render_eval_target(
        cycle_id="feature-custom-dimension",
        stage="decision",
        constraints=constraints,
        registers=init_registers(cycle_id="feature-custom-dimension", stage="decision"),
        payloads={
            "Q": {}, "GL": {}, "E": {}, "D": {},
            "X": {
                "acceptance_criteria": "Active criterion",
                "impact_surface": [{"area": "Inactive built-in sentinel"}],
                "dimension_results": {
                    _CUSTOM: "Active custom sentinel",
                    _INACTIVE: "Inactive custom sentinel",
                },
            },
        },
    )
    assert "Active criterion" in target
    assert "Active custom sentinel" in target
    assert "Inactive custom sentinel" not in target
    assert "Inactive built-in sentinel" not in target
