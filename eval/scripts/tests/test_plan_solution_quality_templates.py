"""Contract tests for Plan's local solution-quality Method and SoT."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remote_ref import read_ref  # noqa: E402
from workflow_layout import project_root_for_refs, workflow_ref, workflow_root  # noqa: E402


_REPO = project_root_for_refs()
_WORKFLOW = workflow_root()
_DIMENSION_DEF = _WORKFLOW / "lulu-plan" / "dimension-defs" / "solution-quality.json"
_RUNNER_SKILL = _WORKFLOW / "eval" / "dimension-probe-runner" / "SKILL.md"
_METHOD_REF = "lulu-workflow/lulu-plan/eval/methods/solution-quality.md"
_SOT_REF = "lulu-workflow/lulu-plan/eval/sots/solution-quality.md"
_P5_FIXTURE = (
    _WORKFLOW
    / "eval"
    / "scripts"
    / "tests"
    / "fixtures"
    / "stage_quality"
    / "p5-contract-underdetermined.md"
)


def test_plan_solution_quality_uses_local_method_and_sot():
    data = json.loads(_DIMENSION_DEF.read_text(encoding="utf-8"))

    assert data["method"] == {
        "ref": _METHOD_REF,
        "focus": "Plan solution quality",
    }
    assert data["sots"] == [{"ref": _SOT_REF}]


def test_plan_local_templates_are_resolvable_from_project_root():
    method = read_ref(workflow_ref(_METHOD_REF), project_root=_REPO)
    sot = read_ref(workflow_ref(_SOT_REF), project_root=_REPO)

    assert "$READ_UNIT_VIEW" in method
    assert "eval_target_units" not in method
    assert "`critical`" in method
    assert "`high`" not in method
    for probe in ("P1", "P2", "P3", "P4", "P5"):
        assert f"## {probe} " in sot
    assert "DECISION-REQUIRED" in method
    assert "root_cause: WO-ERROR" in method
    assert "Do not read upstream documents" in method
    assert "section-registry" not in sot
    assert "section_order" not in sot
    assert "$FETCH_COMPOSE" not in sot


def test_probe_runner_no_longer_defines_intent_gap_probes():
    skill = _RUNNER_SKILL.read_text(encoding="utf-8")
    assert "intent_gap_probes" not in skill
    assert "$READ_UNIT_VIEW" in skill
    assert "read-unit-view" in skill


def test_p5_fixture_leaves_api_shape_underdetermined():
    fixture = _P5_FIXTURE.read_text(encoding="utf-8")

    assert "<!-- chapter: scene-slot -->" in fixture
    assert "API set" in fixture
    assert "includeCorpus" not in fixture
    assert "explicit API list" not in fixture
