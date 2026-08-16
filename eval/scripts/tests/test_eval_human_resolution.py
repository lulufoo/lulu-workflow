#!/usr/bin/env python3
"""Focused Eval control tests for Human Resolution."""

import json
import sys
from pathlib import Path

_EVAL_SCRIPTS = Path(__file__).resolve().parents[1]
_TECH_PLAN_EVAL = _EVAL_SCRIPTS.parents[1] / "lulu-plan" / "scripts" / "eval"
_KERNEL_CORE = _EVAL_SCRIPTS.parents[1] / "compose" / "scripts" / "core"
_KERNEL_SCHEMA_SESSION = (
    _EVAL_SCRIPTS.parents[1] / "compose" / "scripts" / "schema" / "session"
)
_KERNEL_TESTS = _EVAL_SCRIPTS.parents[1] / "compose" / "scripts" / "tests"
for _path in (
    _KERNEL_CORE,
    _KERNEL_SCHEMA_SESSION,
    _KERNEL_TESTS,
    _EVAL_SCRIPTS,
    _TECH_PLAN_EVAL,
):
    sys.path.insert(0, str(_path))

import eval_control  # noqa: E402
from eval_control import (  # noqa: E402
    artifact_remediation_complete,
    begin_artifact_remediation,
    begin_dimension_artifact_remediation,
    begin_dimension_human_resolution,
    check_dimension_human_resolution,
    human_resolution_complete,
    read_b_snapshot_cmd,
    submit_human_resolution,
    submit_remediation_diff,
)
from eval_operation_record_schema import get_operation_record  # noqa: E402
from evaluate_state_ops import (  # noqa: E402
    init_evaluate_state_for_corpus,
    merge_current_dimension,
)
from evaluate_state_schema import load_evaluate_state, save_evaluate_state  # noqa: E402
from init_working_helpers import (  # noqa: E402
    init_working_ready,
    mark_focus_evaluating,
    mark_focus_intake_done,
    product_delivered_refs,
    seed_frozen_delivered,
)
from tech_plan_eval_adapter import TechPlanEvalAdapter  # noqa: E402
from workflow_paths import seed_profile_pointer_for_tests  # noqa: E402
from workflow_state_schema import save_workflow_state  # noqa: E402

_CYCLE = "feat-eval-human-resolution"
_CACHE = Path(".cache/cursor/lulu-dev-workflow")
_ADAPTER = TechPlanEvalAdapter()
_HEADER = (
    "# Tech Review — E2 | revision1 round 1\n\n"
    "**Date:** 2026-01-01\n**Refs:** codebase\n\n"
    "| ID | root_cause | sot_ref | location | severity | evidence | description "
    "| status | decision | resolution |\n"
    "|----|------------|---------|----------|----------|----------|-------------"
    "|--------|----------|------------|\n"
)


def _corpus(tmp_path: Path):
    return _ADAPTER.resolve_eval_corpus(_CYCLE, tmp_path)


def _setup(tmp_path: Path, review_rows: str) -> tuple[Path, Path]:
    base = tmp_path / _CACHE / _CYCLE / "lulu-plan"
    base.mkdir(parents=True)
    (base / "session-state.md").write_text(
        "---\nversion: 1\nactive_doc: 1\nupdated_at: 2024-01-01T00:00:00+00:00\n---\n",
        encoding="utf-8",
    )
    seed_profile_pointer_for_tests(tmp_path, _CYCLE, "lulu-plan")
    workflow_state = base / "revision1" / "workflow-state.md"
    init_working_ready(workflow_state, mode="product")
    seed_frozen_delivered(workflow_state, product_delivered_refs("/p.md"))
    mark_focus_intake_done(workflow_state.parent)
    mark_focus_evaluating(workflow_state.parent)
    save_workflow_state(
        workflow_state,
        {"current_state": "Working", "evaluate_round": "1"},
    )
    target = workflow_state.parent / "L1" / "tech-doc.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Tech Doc\noriginal\n", encoding="utf-8")
    state_path = workflow_state.parent / "L1" / "evaluate-state.md"
    init_evaluate_state_for_corpus(
        state_path,
        _corpus(tmp_path),
        cycle_type="feature",
    )
    state = load_evaluate_state(state_path)
    state = merge_current_dimension(
        state,
        "e2",
        "probed",
        corpus=_corpus(tmp_path),
    )
    state["fix_phase"] = "human-resolution"
    save_evaluate_state(state_path, state, merge=False)
    review_path = workflow_state.parent / "L1" / "evaluate1" / "tech-review-e11.md"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.write_text(_HEADER + review_rows, encoding="utf-8")
    return workflow_state, review_path


def _payload(
    tmp_path: Path,
    *,
    token: str,
    digest: str,
    review_digest: str,
    issue_ids: list[str],
    kind: str,
    resolution: str,
) -> Path:
    path = tmp_path / f"{token}.json"
    path.write_text(
        json.dumps({
            "dimension_token": token,
            "base_digest": digest,
            "review_base_digest": review_digest,
            "resolutions": [{
                "issue_ids": issue_ids,
                "resolution_kind": kind,
                "resolution": resolution,
            }],
        }),
        encoding="utf-8",
    )
    return path


def _set_context():
    adapter_token = eval_control._ADAPTER_CTX.set(_ADAPTER)
    workflow_token = eval_control._WORKFLOW_ID_CTX.set("lulu-plan")
    handoff_token = eval_control._HANDOFF_CTX.set(None)
    return adapter_token, workflow_token, handoff_token


def _reset_context(tokens):
    adapter_token, workflow_token, handoff_token = tokens
    eval_control._ADAPTER_CTX.reset(adapter_token)
    eval_control._WORKFLOW_ID_CTX.reset(workflow_token)
    eval_control._HANDOFF_CTX.reset(handoff_token)


def test_select_reclassifies_decision_for_artifact_without_mutating_b(tmp_path: Path):
    tokens = _set_context()
    try:
        workflow_state, review = _setup(
            tmp_path,
            "| e2-1 | DECISION-REQUIRED | — | tech-doc §2 | critical | ambiguous "
            "| choose an approach | pending | — | |\n",
        )
        target = workflow_state.parent / "L1" / "tech-doc.md"
        human = begin_dimension_human_resolution(_CYCLE, tmp_path, dim="e2")
        snapshot = read_b_snapshot_cmd(
            _CYCLE,
            tmp_path,
            dimension_token=human["operation_ctx"]["dimension_token"],
        )
        result = submit_human_resolution(
            _CYCLE,
            tmp_path,
            payload_file=_payload(
                tmp_path,
                token=human["operation_ctx"]["dimension_token"],
                digest=snapshot["target_digest"],
                review_digest=human["operation_ctx"]["review_base_digest"],
                issue_ids=["e2-1"],
                kind="select",
                resolution="adopt option A",
            ),
        )
        assert result["ok"] is True, result
        assert target.read_text(encoding="utf-8") == "# Tech Doc\noriginal\n"
        assert "| e2-1 | WO-ERROR |" in review.read_text(encoding="utf-8")
        assert "| pending | — | adopt option A |" in review.read_text(encoding="utf-8")
        record = get_operation_record(
            workflow_state.parent / "L1" / "evaluate1" / "eval-operations.json",
            human["operation_ctx"]["dimension_token"],
        )
        assert record["resolution_records"][0]["resolution_kind"] == "select"

        complete = human_resolution_complete(_CYCLE, tmp_path)
        assert complete["fix_phase"] == "artifact-remediation"
        artifact = begin_artifact_remediation(_CYCLE, tmp_path)
        assert artifact["dispatch"] == ["e2"]
        artifact_context = begin_dimension_artifact_remediation(
            _CYCLE,
            tmp_path,
            dim="e2",
        )
        artifact_snapshot = read_b_snapshot_cmd(
            _CYCLE,
            tmp_path,
            dimension_token=artifact_context["operation_ctx"]["dimension_token"],
        )
        remediation = tmp_path / "artifact.json"
        remediation.write_text(
            json.dumps({
                "dimension_token": artifact_context["operation_ctx"]["dimension_token"],
                "base_digest": artifact_snapshot["target_digest"],
                "unified_diff": "@@ -1,2 +1,2 @@\n # Tech Doc\n-original\n+option A\n",
                "issue_ids": ["e2-1"],
            }),
            encoding="utf-8",
        )
        assert submit_remediation_diff(
            _CYCLE,
            tmp_path,
            payload_file=remediation,
        )["ok"] is True
        assert "adopt option A" in review.read_text(encoding="utf-8")
        assert artifact_remediation_complete(_CYCLE, tmp_path)["fix_phase"] == "done"
    finally:
        _reset_context(tokens)


def test_escalation_abandons_round_and_diff_is_rejected(tmp_path: Path):
    tokens = _set_context()
    try:
        workflow_state, _review = _setup(
            tmp_path,
            "| e2-1 | SOT-DEFECT | product §1 | tech-doc §2 | critical | ambiguous "
            "| source conflict | pending | — | |\n",
        )
        human = begin_dimension_human_resolution(_CYCLE, tmp_path, dim="e2")
        snapshot = read_b_snapshot_cmd(
            _CYCLE,
            tmp_path,
            dimension_token=human["operation_ctx"]["dimension_token"],
        )
        bad_diff = tmp_path / "bad-diff.json"
        bad_diff.write_text(
            json.dumps({
                "dimension_token": human["operation_ctx"]["dimension_token"],
                "base_digest": snapshot["target_digest"],
                "unified_diff": "@@ -1,2 +1,2 @@\n # Tech Doc\n-original\n+changed\n",
                "issue_ids": ["e2-1"],
            }),
            encoding="utf-8",
        )
        assert submit_remediation_diff(
            _CYCLE,
            tmp_path,
            payload_file=bad_diff,
        )["ok"] is False
        resolution = submit_human_resolution(
            _CYCLE,
            tmp_path,
            payload_file=_payload(
                tmp_path,
                token=human["operation_ctx"]["dimension_token"],
                digest=snapshot["target_digest"],
                review_digest=human["operation_ctx"]["review_base_digest"],
                issue_ids=["e2-1"],
                kind="escalate",
                resolution="requires product owner decision",
            ),
        )
        assert resolution["ok"] is True, resolution
        assert check_dimension_human_resolution(
            _CYCLE,
            tmp_path,
            dim="e2",
        )["abandoned"] is True
        assert human_resolution_complete(_CYCLE, tmp_path)["abandoned"] is True
        assert load_evaluate_state(
            workflow_state.parent / "L1" / "evaluate-state.md",
        )["eval_status"] == "abandoned"
    finally:
        _reset_context(tokens)
