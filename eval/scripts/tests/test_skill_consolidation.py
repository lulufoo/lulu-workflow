"""Structural contracts for consolidated Eval SKILL workflows."""

from pathlib import Path


_WORKFLOW = Path(__file__).resolve().parents[3]
_EVAL_ROOT = _WORKFLOW / "eval"
_ORCHESTRATOR = _EVAL_ROOT / "SKILL.md"
_PROBE_RUNNER = _EVAL_ROOT / "dimension-probe-runner" / "SKILL.md"
_REMEDIATION_RUNNER = _EVAL_ROOT / "remediation-runner" / "SKILL.md"
_CURRENT_SKILLS = (
    _ORCHESTRATOR,
    _PROBE_RUNNER,
    _REMEDIATION_RUNNER,
)
_REMOVED_RUNNERS = (
    _EVAL_ROOT / "human-resolution-runner",
    _EVAL_ROOT / "artifact-remediation-runner",
    _EVAL_ROOT / "eval-probe-runner",
    _EVAL_ROOT / "eval-artifact-remediation-runner",
    _EVAL_ROOT / "eval-sot-remediation-runner",
)
_LEGACY_COMMANDS = (
    "begin-human-resolution",
    "begin-dimension-human-resolution",
    "submit-human-resolution",
    "check-dimension-human-resolution",
    "human-resolution-complete",
    "begin-artifact-remediation",
    "begin-dimension-artifact-remediation",
    "submit-remediation-diff",
    "check-dimension-artifact-remediation",
    "artifact-remediation-complete",
    "probe-complete",
    "complete-round",
)
_LEGACY_SKILL_MARKERS = (
    "force_human_resolution",
    "## Human Resolution",
    "## Artifact Remediation",
    "human-resolution-runner",
    "artifact-remediation-runner",
)


def _skill_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_eval_skills_are_consolidated_and_macro_only() -> None:
    assert not (_EVAL_ROOT / "eval-rules.md").exists()
    assert not any(path.exists() for path in _REMOVED_RUNNERS)

    for skill in _CURRENT_SKILLS:
        text = _skill_text(skill)
        assert "## Script Macros" in text
        assert "review_schema.py" not in text
        assert "issue-taxonomy.json" not in text
        if skill == _ORCHESTRATOR:
            assert 'python3 "$SKILL_ROOT/eval/scripts/eval_entry.py"' in text
            body = text.split("## Principles", 1)[1]
            assert "python3" not in body
        else:
            assert "python3" not in text


def test_eval_orchestrator_is_probe_then_remediation_then_complete() -> None:
    text = _skill_text(_ORCHESTRATOR)
    begin = text.index("## Begin Eval")
    remediation = text.index("## Remediation")
    completion = text.index("## Completion")
    abandon = text.index("## Abandon Handler")
    assert begin < remediation < completion < abandon

    begin_section = text[begin:remediation]
    rem_section = text[remediation:completion]
    abandon_section = text[abandon:]

    assert "complete-probe-only" in begin_section
    assert "probe-only" in begin_section.lower()
    assert "skip: true" in begin_section
    assert "skip_reason" in begin_section
    assert "Do not run `check-dimension` for a skipped dimension." in begin_section
    assert "dimension-probe-runner" in text
    assert "serially" in rem_section
    assert "begin-remediation" in rem_section
    assert "begin-dimension-remediation" in rem_section
    assert "check-dimension-remediation" in rem_section
    assert "remediation-complete" in rem_section
    assert "remediation-runner" in rem_section
    assert "Do not dispatch remaining dimensions" in abandon_section
    assert "Leave the L in Evaluating" in abandon_section
    assert "$L_STEP" not in text
    assert "The caller owns the L transition." in text

    for marker in _LEGACY_SKILL_MARKERS:
        assert marker not in text
    for command in _LEGACY_COMMANDS:
        assert command not in text


def test_remediation_runner_prepares_then_gates_then_applies() -> None:
    text = _skill_text(_REMEDIATION_RUNNER)
    assert "prepare-remediation" in text
    assert "apply-remediation" in text
    assert text.index("prepare-remediation") < text.index("apply-remediation")
    assert "human-gated" in text
    assert "human_gate" in text
    assert "null" in text
    assert "Do not write B, ReviewFile, evaluate-state, or operation records" in text
    assert "Do not dispatch subagents" in text
    for command in _LEGACY_COMMANDS:
        assert command not in text
    for marker in (
        "force_human_resolution",
        "human-resolution-runner",
        "artifact-remediation-runner",
        "submit-human-resolution",
        "submit-remediation-diff",
    ):
        assert marker not in text


def test_remediation_runner_uses_operation_token_from_dispatch_input() -> None:
    runner = _skill_text(_REMEDIATION_RUNNER)
    assert "OPERATION_TOKEN" in runner
    assert "$DIMENSION_TOKEN" not in runner
    assert "--operation-token" in runner

    orchestrator = _skill_text(_ORCHESTRATOR)
    rem_section = orchestrator[
        orchestrator.index("## Remediation") : orchestrator.index("## Completion")
    ]
    assert "OPERATION_TOKEN" in rem_section
    assert "dispatch_input" in rem_section


def test_probe_runner_does_not_interpret_handling_policy() -> None:
    text = _skill_text(_PROBE_RUNNER)
    assert "force_human_resolution" not in text
    assert "Do not read or interpret HandlingPolicy / handling_mode" in text
    assert "classify exactly as the resolved method requires" in text
    for command in _LEGACY_COMMANDS:
        assert command not in text
