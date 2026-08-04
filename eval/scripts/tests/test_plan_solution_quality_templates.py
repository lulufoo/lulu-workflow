"""Contract tests for Plan's local solution-quality Method and SoT."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from url_fetch import read_ref  # noqa: E402


_REPO = Path(__file__).resolve().parents[4]
_WORKFLOW = _REPO / "lulu-dev-workflow"
_DIMENSION_DEF = _WORKFLOW / "lulu-plan" / "dimension-defs" / "solution-quality.json"
_RUNNER_SKILL = _WORKFLOW / "eval" / "eval-probe-runner" / "SKILL.md"
_METHOD_REF = "lulu-dev-workflow/lulu-plan/eval/methods/solution-quality.md"
_SOT_REF = "lulu-dev-workflow/lulu-plan/eval/sots/solution-quality.md"


def test_plan_solution_quality_uses_local_method_and_sot():
    data = json.loads(_DIMENSION_DEF.read_text(encoding="utf-8"))

    assert data["method"] == {
        "kind": "external",
        "source": _METHOD_REF,
        "focus": "Plan solution quality",
    }
    assert data["sots"] == [{"kind": "url", "role": "primary", "ref": _SOT_REF}]


def test_plan_local_templates_are_resolvable_from_project_root():
    method = read_ref(_METHOD_REF, project_root=_REPO)
    sot = read_ref(_SOT_REF, project_root=_REPO)

    assert "eval_target_units.units_from_eval_target(B_text)" in method
    assert "`critical`" in method
    assert "`high`" not in method
    for probe in ("P1", "P2", "P3", "P4"):
        assert f"## {probe} " in sot
    assert "section-registry" not in sot
    assert "section_order" not in sot
    assert "$FETCH_COMPOSE" not in sot


def test_probe_runner_no_longer_defines_intent_gap_probes():
    assert "intent_gap_probes" not in _RUNNER_SKILL.read_text(encoding="utf-8")
