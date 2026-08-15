"""Contract tests for local Design, Architecture, and Blueprint templates."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from review_io import parse_review_file  # noqa: E402
from review_schema import validate_review_file  # noqa: E402
from url_fetch import read_ref  # noqa: E402


_REPO = Path(__file__).resolve().parents[4]
_WORKFLOW = _REPO / "lulu-dev-workflow"
_STAGE_CONFIGS = _REPO / "skill-config" / "lulu-dev-workflow" / "stages"
_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "stage_quality"

_STAGES = (
    {
        "id": "lulu-design",
        "dimension": "solution-quality",
        "method": "lulu-dev-workflow/lulu-design/eval/methods/solution-quality.md",
        "sot": "lulu-dev-workflow/lulu-design/eval/sots/solution-quality.md",
        "focus": "Design solution quality",
        "supplements": ("D1", "D2", "D3", "D4"),
        "legacy_config": "tdt_design_quality_framework_url",
        "adapter": "lulu-design/scripts/eval/tech_design_eval_adapter.py",
    },
    {
        "id": "lulu-arch",
        "dimension": "arch-quality",
        "method": "lulu-dev-workflow/lulu-arch/eval/methods/arch-quality.md",
        "sot": "lulu-dev-workflow/lulu-arch/eval/sots/arch-quality.md",
        "focus": "Architecture quality",
        "supplements": ("A1", "A2", "A3", "A4", "A5"),
        "legacy_config": "tat_arch_quality_framework_url",
        "adapter": "lulu-arch/scripts/eval/tech_arch_eval_adapter.py",
    },
    {
        "id": "lulu-blueprint",
        "dimension": "blueprint-quality",
        "method": "lulu-dev-workflow/lulu-blueprint/eval/methods/blueprint-quality.md",
        "sot": "lulu-dev-workflow/lulu-blueprint/eval/sots/blueprint-quality.md",
        "focus": "Blueprint quality",
        "supplements": ("A1", "A2", "A3", "A4", "A5"),
        "legacy_config": "pbt_blueprint_quality_framework_url",
        "adapter": "lulu-blueprint/scripts/eval/product_blueprint_eval_adapter.py",
    },
)


@pytest.mark.parametrize("stage", _STAGES, ids=lambda stage: stage["id"])
def test_stage_quality_uses_resolvable_local_method_and_sot(stage):
    dimension_path = (
        _WORKFLOW / stage["id"] / "dimension-defs" / f"{stage['dimension']}.json"
    )
    dimension = json.loads(dimension_path.read_text(encoding="utf-8"))

    assert dimension["method"] == {
        "ref": stage["method"],
        "focus": stage["focus"],
    }
    assert dimension["sots"] == [{"ref": stage["sot"]}]

    method = read_ref(stage["method"], project_root=_REPO)
    sot = read_ref(stage["sot"], project_root=_REPO)
    assert "eval_target_units.units_from_eval_target(B_text)" in method
    assert "prior_container_units(view, container_id)" in method
    assert "`critical`" in method
    assert "`high`" not in method
    for probe in ("P1", "P2", "P3", "P4"):
        assert f"## {probe} " in sot
    for supplement in stage["supplements"]:
        assert f"### {supplement} " in sot
    assert "section-registry" not in sot
    assert "section_order" not in sot
    assert "$FETCH_COMPOSE" not in sot


@pytest.mark.parametrize("stage", _STAGES, ids=lambda stage: stage["id"])
def test_stage_quality_removes_legacy_remote_framework_bind(stage):
    config = json.loads(
        (_STAGE_CONFIGS / f"{stage['id']}.json").read_text(encoding="utf-8")
    )
    assert stage["legacy_config"] not in config.get("eval", {})
    assert stage["legacy_config"] not in (
        _WORKFLOW / stage["adapter"]
    ).read_text(encoding="utf-8")


def test_stage_quality_behavior_fixtures_match_their_expected_register_violation():
    expected = json.loads(
        (_FIXTURE_DIR / "expected_findings.json").read_text(encoding="utf-8")
    )
    stage_by_id = {stage["id"]: stage for stage in _STAGES}

    for case in expected:
        content = (_FIXTURE_DIR / case["fixture"]).read_text(encoding="utf-8")
        sot = read_ref(stage_by_id[case["stage"]]["sot"], project_root=_REPO)

        assert f"### {case['expected_sot_rule']} " in sot
        assert "<!-- chapter:" in content
        assert "- [ ]" in content

        review_path = _FIXTURE_DIR / case["review_file"]
        assert validate_review_file(review_path) == []
        rows = parse_review_file(review_path)
        assert len(rows) == 1
        assert rows[0]["sot_ref"].endswith(f"#{case['expected_sot_rule']}")
        assert rows[0]["location"] == case["expected_location"]
        assert rows[0]["severity"] == "critical"

        p1_p4_review_path = _FIXTURE_DIR / case["p1_p4_review_file"]
        assert validate_review_file(p1_p4_review_path) == []
        p1_p4_rows = parse_review_file(p1_p4_review_path)
        assert [row["sot_ref"].rsplit("#", maxsplit=1)[-1] for row in p1_p4_rows] == [
            "P1",
            "P2",
            "P3",
            "P4",
        ]
