"""Focused Slice 2A tests for unified Eval Control behavior."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval_control import (  # noqa: E402
    _load_probe_payload,
    _render_probe_review,
    allowed_decisions_for_issue,
    build_parser,
    handling_mode_for_issue,
    prepare_remediation_at,
)
from eval_operation_record_schema import (  # noqa: E402
    cancel_operation_record,
    create_remediation_operation_record,
    get_operation_record,
)
from review_io import parse_review_content  # noqa: E402


_TARGET_DIGEST = "a" * 64
_REVIEW_DIGEST = "b" * 64
_DIFF = "--- a/target.md\n+++ b/target.md\n@@ -1 +1 @@\n-old\n+new\n"


def _operation() -> dict:
    return {
        "round_token": "round-1",
        "operation_token": "operation-1",
        "dimension_id": "quality",
        "operation_kind": "remediation",
        "phase": "context-open",
        "target_base_digest": _TARGET_DIGEST,
        "review_before_exists": True,
        "review_base_digest": _REVIEW_DIGEST,
        "required_issue_ids": ["a-1", "h-1"],
        "handling_modes_by_issue": {
            "a-1": "direct",
            "h-1": "human-gated",
        },
        "allowed_decisions_by_issue": {
            "a-1": ["fix"],
            "h-1": ["fix", "accept-divergence", "escalate"],
        },
        "submission_digest": None,
        "target_effect": None,
        "target_after_digest": None,
        "review_after_digest": None,
        "target_lease_key": "/target.md",
    }


def _proposal() -> dict:
    return {
        "round_token": "round-1",
        "operation_token": "operation-1",
        "target_base_digest": _TARGET_DIGEST,
        "review_base_digest": _REVIEW_DIGEST,
        "proposals": [
            {
                "issue_id": "h-1",
                "proposed_decision": "accept-divergence",
                "resolution": "intentional difference",
            },
            {
                "issue_id": "a-1",
                "proposed_decision": "fix",
                "resolution": "apply correction",
            },
        ],
        "mutation": {
            "issue_ids": ["a-1"],
            "unified_diff": _DIFF,
        },
    }


def _persist_operation(path: Path) -> None:
    operation = _operation()
    create_remediation_operation_record(
        path,
        operation_token=operation["operation_token"],
        round_token=operation["round_token"],
        dimension_id=operation["dimension_id"],
        target_lease_key=operation["target_lease_key"],
        capture_record=lambda: operation,
    )


@pytest.mark.parametrize(
    ("policy", "root_cause", "expected"),
    [
        ("class-default", "WO-MISS", "direct"),
        ("class-default", "WO-ERROR", "direct"),
        ("class-default", "SOT-DEFECT", "human-gated"),
        ("class-default", "UNRESOLVABLE", "human-gated"),
        ("class-default", "DECISION-REQUIRED", "human-gated"),
        ("human-first", "WO-MISS", "human-gated"),
        ("human-first", "SOT-DEFECT", "human-gated"),
    ],
)
def test_control_owns_handling_mode_mapping(
    policy: str,
    root_cause: str,
    expected: str,
):
    assert handling_mode_for_issue(root_cause, policy) == expected


def test_probe_rejects_caller_supplied_handling_mode(tmp_path: Path):
    payload_path = tmp_path / "probe.json"
    payload_path.write_text(
        json.dumps({
            "dimension_token": "probe-1",
            "findings": [{
                "id": "q-1",
                "root_cause": "WO-ERROR",
                "handling_mode": "human-gated",
                "location": "target.md:1",
                "severity": "medium",
                "evidence": "old",
                "description": "incorrect",
            }],
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="handling_mode"):
        _load_probe_payload(payload_path)


def test_probe_review_stamps_v3_identity_and_modes():
    content = _render_probe_review(
        dimension_label="Quality",
        dimension_id="quality",
        round_token="round-1",
        active_doc=1,
        evaluate_round=1,
        method_focus="quality",
        handling_policy="class-default",
        findings=[
            {
                "id": "q-1",
                "root_cause": "WO-ERROR",
                "location": "target.md:1",
                "severity": "medium",
                "evidence": "old",
                "description": "incorrect",
            },
            {
                "id": "q-2",
                "root_cause": "SOT-DEFECT",
                "sot_ref": "spec.md",
                "location": "target.md:2",
                "severity": "critical",
                "evidence": "conflict",
                "description": "upstream defect",
            },
        ],
    )

    rows = parse_review_content(
        content,
        expected_dimension_id="quality",
        expected_round_token="round-1",
    )
    assert [row["handling_mode"] for row in rows] == ["direct", "human-gated"]


def test_mixed_issue_authorization_is_control_owned():
    assert allowed_decisions_for_issue("WO-ERROR", "direct") == ["fix"]
    assert allowed_decisions_for_issue("WO-ERROR", "human-gated") == [
        "fix",
        "accept-divergence",
        "escalate",
    ]
    assert allowed_decisions_for_issue("DECISION-REQUIRED", "human-gated") == [
        "select",
        "allow-multiple",
        "escalate",
    ]
    assert allowed_decisions_for_issue("SOT-DEFECT", "human-gated") == ["escalate"]


def test_prepare_is_repeatable_and_writes_nothing(tmp_path: Path):
    operations_path = tmp_path / "eval-operations.json"
    proposal_path = tmp_path / "proposal.json"
    _persist_operation(operations_path)
    proposal_path.write_text(json.dumps(_proposal()), encoding="utf-8")
    before_files = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    first = prepare_remediation_at(
        operations_path=operations_path,
        proposal_file=proposal_path,
    )
    second = prepare_remediation_at(
        operations_path=operations_path,
        proposal_file=proposal_path,
    )

    after_files = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    assert first == second
    assert first["proposal"]["proposals"][0]["issue_id"] == "a-1"
    assert before_files == after_files
    assert get_operation_record(operations_path, "operation-1") == _operation()


def test_prepare_rejects_operation_after_context_open(tmp_path: Path):
    operations_path = tmp_path / "eval-operations.json"
    proposal_path = tmp_path / "proposal.json"
    _persist_operation(operations_path)
    cancel_operation_record(operations_path, "operation-1")
    proposal_path.write_text(json.dumps(_proposal()), encoding="utf-8")

    with pytest.raises(ValueError, match="context-open"):
        prepare_remediation_at(
            operations_path=operations_path,
            proposal_file=proposal_path,
        )


def test_parser_exposes_unified_routes_and_removes_legacy_routes():
    parser = build_parser()
    choices = parser._subparsers._group_actions[0].choices
    expected = {
        "begin-remediation",
        "begin-dimension-remediation",
        "cancel-remediation",
        "prepare-remediation",
        "apply-remediation",
        "check-dimension-remediation",
        "remediation-complete",
        "complete-probe-only",
    }
    legacy = {
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
    }
    assert expected <= set(choices)
    assert legacy.isdisjoint(choices)
