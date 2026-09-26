"""Tests for Compose's private-to-generic Eval handoff translation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_EVAL_SCRIPTS = Path(__file__).resolve().parents[1]
_COMPOSE_CORE = _EVAL_SCRIPTS.parents[1] / "compose" / "scripts" / "eval"
for path in (_EVAL_SCRIPTS, _COMPOSE_CORE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import compose_eval_adapter
from compose_eval_adapter import ComposeEvalAdapter
from eval_handoff_schema import validate_eval_handoff_v2
from stage_eval_contributor import StageEvalContribution, validate_contribution


class _Dummy:
    def contribute(self, *, context):
        del context
        return StageEvalContribution(
            dimensions=[{"id": "x"}],
            bindings={},
            review_output_prefix="design-review",
        )


def _adapter() -> ComposeEvalAdapter:
    return ComposeEvalAdapter(workflow_id="lulu-design", contributor=_Dummy())


def test_validate_contribution_rejects_empty_binding() -> None:
    with pytest.raises(ValueError, match="non-empty string"):
        validate_contribution(
            StageEvalContribution(
                dimensions=[{"id": "stage-dim"}],
                bindings={"upstream_baseline_ref": ""},
                review_output_prefix="design-review",
            )
        )


def test_request_handoff_translates_compose_context_to_generic_v2(
    monkeypatch,
    tmp_path: Path,
) -> None:
    legacy_context = {
        "cycle_id": "cycle-1",
        "profile_id": "lulu-design",
        "execution_fingerprint": "private-execution-fingerprint",
        "eval_run_id": "run-1",
        "evaluate_round": 2,
        "revision_dir": "/tmp/revision1",
        "execution_dir": "/tmp/revision1/execution",
        "compose_doc": "/tmp/revision1/execution/design-doc.md",
        "evaluate_state_path": "/tmp/revision1/execution/evaluate-state.md",
        "evaluate_dir": "/tmp/revision1/execution/evaluate2",
        "write_staging_dir": "/tmp/revision1/execution/.eval-staging/lease-1",
        "lease_id": "lease-1",
        "policy_context": {
            "mode": "tech",
            "cycle_type": "feature",
            "upstream_baseline_ref": "",
            "eval_capability": "full-remediation",
        },
    }
    monkeypatch.setattr(
        compose_eval_adapter,
        "request_handoff",
        lambda *args, **kwargs: {"ok": True, "handoff": {"context": legacy_context}},
    )

    handoff = _adapter().request_eval_handoff("cycle-1", tmp_path)

    assert validate_eval_handoff_v2(handoff) == []
    assert handoff["context"]["workflow_id"] == "lulu-design"
    assert handoff["context"]["cycle_id"] == "cycle-1"
    assert handoff["context"]["session_key"] == "lulu-design"
    assert handoff["context"]["bindings"] == {
        "eval_target_path": "/tmp/revision1/execution/design-doc.md",
    }
    assert handoff["context"]["policy_context"]["eval_capability"] == "full-remediation"
    assert {"compose_doc", "focus_l", "ledger_fingerprint"}.isdisjoint(
        handoff["context"],
    )
