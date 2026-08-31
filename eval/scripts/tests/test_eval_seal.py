"""Seal contracts for the Eval script-layer reorg (framework §9)."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import eval_control  # noqa: E402
from eval_control import build_parser  # noqa: E402


_EVAL_SCRIPTS = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = _EVAL_SCRIPTS.parents[1]
_COMMAND_FORWARD = {
    "init_round": "round_control",
    "begin_eval_round": "round_control",
    "complete_probe_only": "round_control",
    "begin_dimension": "probe_control",
    "read_b_snapshot_cmd": "probe_control",
    "read_unit_view_cmd": "probe_control",
    "read_evidence_snapshot_cmd": "probe_control",
    "submit_probe_findings": "probe_control",
    "check_dimension": "probe_control",
    "begin_remediation": "remediation_control",
    "begin_dimension_remediation": "remediation_control",
    "cancel_remediation": "remediation_control",
    "prepare_remediation": "remediation_control",
    "apply_remediation": "remediation_control",
    "check_dimension_remediation": "remediation_control",
    "remediation_complete": "remediation_control",
}


def test_all_cli_commands_forward_to_family_control() -> None:
    choices = set(build_parser()._subparsers._group_actions[0].choices)
    assert choices == {
        "init-round",
        "begin-eval-round",
        "begin-dimension",
        "read-b-snapshot",
        "read-evidence-snapshot",
        "submit-probe-findings",
        "check-dimension",
        "read-unit-view",
        "begin-remediation",
        "begin-dimension-remediation",
        "cancel-remediation",
        "prepare-remediation",
        "apply-remediation",
        "check-dimension-remediation",
        "remediation-complete",
        "complete-probe-only",
    }
    for name, module in _COMMAND_FORWARD.items():
        source = inspect.getsource(getattr(eval_control, name))
        assert f"import {module}" in source
        assert f"return {module}." in source


def test_eval_methods_do_not_name_script_files() -> None:
    methods = sorted(_WORKFLOW_ROOT.rglob("eval/methods/*.md"))
    assert len(methods) == 10
    banned = ("eval/scripts", "eval_target_units", ".py")
    for path in methods:
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path}: {token}"


def test_callers_enter_through_eval_entry() -> None:
    compose = (
        _WORKFLOW_ROOT / "compose" / "scripts" / "eval" / "compose_eval_control.py"
    ).read_text(encoding="utf-8")
    assert 'eval" / "scripts" / "eval_entry.py"' in compose
    decision = (
        _WORKFLOW_ROOT
        / "decision"
        / "runners"
        / "dc-delivery-runner"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    assert "eval/scripts/eval_entry.py" in decision
    assert "eval/scripts/eval_control.py" not in decision


def test_eval_control_main_rejects_direct_invocation(capsys) -> None:
    assert eval_control.main() == 1
    assert "eval_entry.py" in capsys.readouterr().err
