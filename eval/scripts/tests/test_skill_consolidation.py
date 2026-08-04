"""Structural contracts for consolidated Eval SKILL workflows."""

from pathlib import Path


_WORKFLOW = Path(__file__).resolve().parents[3]
_EVAL_ROOT = _WORKFLOW / "eval"
_SKILLS = (
    _EVAL_ROOT / "SKILL.md",
    _EVAL_ROOT / "dimension-probe-runner" / "SKILL.md",
    _EVAL_ROOT / "artifact-remediation-runner" / "SKILL.md",
    _EVAL_ROOT / "human-resolution-runner" / "SKILL.md",
)
_LEGACY_RUNNERS = (
    _EVAL_ROOT / "eval-probe-runner",
    _EVAL_ROOT / "eval-artifact-remediation-runner",
    _EVAL_ROOT / "eval-sot-remediation-runner",
)


def test_eval_skills_are_consolidated_and_macro_only() -> None:
    assert not (_EVAL_ROOT / "eval-rules.md").exists()
    assert not any(path.is_dir() for path in _LEGACY_RUNNERS)

    for skill in _SKILLS:
        text = skill.read_text(encoding="utf-8")
        assert "## Script Macros" in text
        assert "python3" not in text
        assert "review_schema.py" not in text
        assert "issue-taxonomy.json" not in text
