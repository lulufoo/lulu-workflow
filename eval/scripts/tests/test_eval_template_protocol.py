"""Contract tests for the unified Eval Method and SoT template protocol."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remote_ref import read_ref  # noqa: E402
from workflow_layout import project_root_for_refs, workflow_ref, workflow_root  # noqa: E402


_REPO = project_root_for_refs()
_WORKFLOW = workflow_root()
_ACTIVE_DEFINITIONS = (
    "lulu-plan/dimension-defs/codebase-consistency.json",
    "lulu-plan/dimension-defs/solution-quality.json",
    "lulu-design/dimension-defs/codebase-consistency.json",
    "lulu-design/dimension-defs/solution-quality.json",
    "compose/eval/dimension-defs/intent-fidelity.json",
    "compose/eval/dimension-defs/scope-continuity.json",
    "compose/eval/dimension-defs/norm-conformance.json",
    "lulu-spec/dimension-defs/product-doc-quality.json",
    "lulu-arch/dimension-defs/arch-quality.json",
    "lulu-blueprint/dimension-defs/blueprint-quality.json",
    "decision/eval/dimension-defs/decision-consistency.json",
)


@pytest.mark.parametrize("relative_path", _ACTIVE_DEFINITIONS)
def test_active_eval_dimensions_use_only_template_refs(relative_path: str):
    definition = json.loads((_WORKFLOW / relative_path).read_text(encoding="utf-8"))

    method = definition["method"]
    assert set(method) == {"ref", "focus"}
    assert read_ref(workflow_ref(method["ref"]), project_root=_REPO).strip()

    for sot in definition["sots"]:
        assert set(sot) == {"ref"}
        if sot["ref"] != "." and not sot["ref"].startswith("{"):
            assert read_ref(workflow_ref(sot["ref"]), project_root=_REPO).strip()


def test_shared_codebase_consistency_method_defines_the_evidence_contract():
    method = read_ref(
        workflow_ref("lulu-workflow/eval/methods/codebase-consistency.md"),
        project_root=_REPO,
    )

    assert "explicit code claims" in method
    assert "evidence basis" in method
