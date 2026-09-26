"""Tests for pure RemediationProposal and RemediationApplication contracts."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from remediation_schema import (  # noqa: E402
    application_submission_digest,
    canonicalize_remediation_application,
    canonicalize_remediation_proposal,
    final_digest,
    prepare_remediation_proposal,
    proposal_digest,
    validate_remediation_application,
    validate_remediation_proposal,
)

_DIGEST = "a" * 64
_DIFF = "--- a/target.md\n+++ b/target.md\n@@ -1 +1 @@\n-old\n+new\n"


def _operation(*, mixed: bool = False, phase: str = "context-open") -> dict:
    issue_ids = ["e2-1", "e2-2"] if mixed else ["e2-1"]
    return {
        "round_token": "round-1",
        "operation_token": "operation-1",
        "dimension_id": "synthetic-quality",
        "operation_kind": "remediation",
        "phase": phase,
        "target_base_digest": _DIGEST,
        "review_base_digest": "b" * 64,
        "required_issue_ids": issue_ids,
        "handling_modes_by_issue": {
            "e2-1": "direct",
            **({"e2-2": "human-gated"} if mixed else {}),
        },
        "allowed_decisions_by_issue": {
            "e2-1": ["fix"],
            **(
                {"e2-2": ["fix", "accept-divergence", "escalate"]}
                if mixed
                else {}
            ),
        },
        "submission_digest": None,
        "target_effect": None,
        "target_after_digest": None,
        "review_after_digest": None,
    }


def _candidate(*, mixed: bool = False) -> dict:
    proposals = [{
        "issue_id": "e2-1",
        "proposed_decision": "fix",
        "resolution": "apply direct correction",
    }]
    issue_ids = ["e2-1"]
    if mixed:
        proposals.append({
            "issue_id": "e2-2",
            "proposed_decision": "fix",
            "resolution": "apply gated correction",
        })
        issue_ids.append("e2-2")
    return {
        "round_token": "round-1",
        "operation_token": "operation-1",
        "target_base_digest": _DIGEST,
        "review_base_digest": "b" * 64,
        "proposals": proposals,
        "mutation": {"issue_ids": issue_ids, "unified_diff": _DIFF},
    }


def _prepared(*, mixed: bool = False) -> dict:
    return prepare_remediation_proposal(_operation(mixed=mixed), _candidate(mixed=mixed))[
        "proposal"
    ]


def _direct_application() -> dict:
    proposal = _prepared()
    return {
        "proposal": proposal,
        "human_gate": None,
        "final": {
            "outcome": "apply",
            "resolutions": [{
                "issue_id": "e2-1",
                "decision": "fix",
                "resolution": "apply direct correction",
            }],
            "mutation": copy.deepcopy(proposal["mutation"]),
        },
    }


def _mixed_application(*, changed_diff: bool = False) -> dict:
    operation = _operation(mixed=True)
    proposal = _prepared(mixed=True)
    final = {
        "outcome": "apply",
        "resolutions": [
            {
                "issue_id": "e2-1",
                "decision": "fix",
                "resolution": "apply direct correction",
            },
            {
                "issue_id": "e2-2",
                "decision": "fix",
                "resolution": "human confirmed correction",
            },
        ],
        "mutation": copy.deepcopy(proposal["mutation"]),
    }
    if changed_diff:
        final["mutation"]["unified_diff"] = _DIFF.replace("+new", "+human-new")
    return {
        "proposal": proposal,
        "human_gate": {
            "proposal_digest": proposal_digest(operation, proposal),
            "final_digest": final_digest(operation, final),
            "issue_ids": ["e2-2"],
            "actor": "human",
            "recorded_at": "2026-08-16T13:00:00+08:00",
            "approves_full_mutation": changed_diff,
        },
        "final": final,
    }


class TestRemediationProposal:
    def test_prepare_is_repeatable_pure_and_returns_digest(self):
        operation = _operation()
        candidate = _candidate()
        before_operation = copy.deepcopy(operation)
        before_candidate = copy.deepcopy(candidate)
        first = prepare_remediation_proposal(operation, candidate)
        second = prepare_remediation_proposal(operation, candidate)
        assert first == second
        assert operation == before_operation
        assert candidate == before_candidate
        assert first["proposal_digest"] == proposal_digest(
            operation,
            first["proposal"],
        )

    def test_prepare_requires_context_open(self):
        with pytest.raises(ValueError, match="context-open"):
            prepare_remediation_proposal(
                _operation(phase="prepared"),
                _candidate(),
            )

    def test_proposal_must_cover_every_required_issue_once(self):
        candidate = _candidate(mixed=True)
        candidate["proposals"].pop()
        errors = validate_remediation_proposal(_operation(mixed=True), candidate)
        assert any("exactly cover required_issue_ids" in error for error in errors)

    def test_direct_issue_can_only_use_pre_authorized_decision(self):
        candidate = _candidate()
        candidate["proposals"][0]["proposed_decision"] = "accept-divergence"
        errors = validate_remediation_proposal(_operation(), candidate)
        assert any("direct issue" in error for error in errors)

    def test_proposal_mutation_ids_equal_all_mutating_decisions(self):
        candidate = _candidate(mixed=True)
        candidate["proposals"][1]["proposed_decision"] = "accept-divergence"
        errors = validate_remediation_proposal(_operation(mixed=True), candidate)
        assert any("mutation.issue_ids" in error for error in errors)
        candidate["mutation"]["issue_ids"] = ["e2-1"]
        assert validate_remediation_proposal(_operation(mixed=True), candidate) == []

    def test_no_mutating_decisions_require_null_mutation(self):
        operation = _operation(mixed=True)
        operation["required_issue_ids"] = ["e2-2"]
        operation["handling_modes_by_issue"] = {"e2-2": "human-gated"}
        operation["allowed_decisions_by_issue"] = {
            "e2-2": ["accept-divergence", "escalate"],
        }
        candidate = _candidate(mixed=True)
        candidate["proposals"] = [{
            "issue_id": "e2-2",
            "proposed_decision": "accept-divergence",
            "resolution": "intentional",
        }]
        candidate["mutation"] = None
        assert validate_remediation_proposal(operation, candidate) == []

    def test_proposal_digest_and_canonicalization_follow_required_issue_order(self):
        operation = _operation(mixed=True)
        candidate = _candidate(mixed=True)
        reordered = copy.deepcopy(candidate)
        reordered["proposals"].reverse()
        reordered["mutation"]["issue_ids"].reverse()
        assert proposal_digest(operation, reordered) == proposal_digest(
            operation,
            candidate,
        )
        assert canonicalize_remediation_proposal(
            operation,
            reordered,
        )["proposals"] == candidate["proposals"]


class TestApplyApplication:
    def test_all_direct_final_must_equal_proposal(self):
        application = _direct_application()
        assert validate_remediation_application(_operation(), application) == []
        application["final"]["resolutions"][0]["resolution"] = "rewritten"
        assert any(
            "all-direct final must equal proposal" in error
            for error in validate_remediation_application(_operation(), application)
        )

    def test_human_gate_can_modify_gated_result_but_not_direct_result(self):
        application = _mixed_application(changed_diff=True)
        assert validate_remediation_application(
            _operation(mixed=True),
            application,
        ) == []
        application["final"]["resolutions"][0]["resolution"] = "changed direct"
        application["human_gate"]["final_digest"] = final_digest(
            _operation(mixed=True),
            application["final"],
        )
        assert any(
            "direct issue" in error
            for error in validate_remediation_application(
                _operation(mixed=True),
                application,
            )
        )

    def test_human_gate_is_required_and_binds_proposal_and_final_digests(self):
        operation = _operation(mixed=True)
        application = _mixed_application()
        application["human_gate"] = None
        assert any(
            "human_gate is required" in error
            for error in validate_remediation_application(operation, application)
        )

        application = _mixed_application()
        application["human_gate"]["proposal_digest"] = "0" * 64
        assert any(
            "proposal_digest mismatch" in error
            for error in validate_remediation_application(operation, application)
        )

        application = _mixed_application()
        application["human_gate"]["final_digest"] = "0" * 64
        assert any(
            "final_digest mismatch" in error
            for error in validate_remediation_application(operation, application)
        )

    def test_changed_global_diff_requires_full_mutation_approval(self):
        application = _mixed_application(changed_diff=True)
        application["human_gate"]["approves_full_mutation"] = False
        assert any(
            "approves_full_mutation" in error
            for error in validate_remediation_application(
                _operation(mixed=True),
                application,
            )
        )

    def test_apply_revalidates_embedded_proposal(self):
        application = _direct_application()
        application["proposal"]["proposals"][0]["proposed_decision"] = "select"
        assert any(
            "embedded proposal invalid" in error
            for error in validate_remediation_application(_operation(), application)
        )

    @pytest.mark.parametrize("decision", ["fix", "select", "allow-multiple"])
    def test_mutating_decisions_require_exact_mutation_coverage(self, decision: str):
        operation = _operation(mixed=True)
        operation["required_issue_ids"] = ["e2-2"]
        operation["handling_modes_by_issue"] = {"e2-2": "human-gated"}
        operation["allowed_decisions_by_issue"] = {"e2-2": [decision]}
        proposal = {
            **_candidate(mixed=True),
            "proposals": [{
                "issue_id": "e2-2",
                "proposed_decision": decision,
                "resolution": "proposed",
            }],
            "mutation": {"issue_ids": ["e2-2"], "unified_diff": _DIFF},
        }
        final = {
            "outcome": "apply",
            "resolutions": [{
                "issue_id": "e2-2",
                "decision": decision,
                "resolution": "confirmed",
            }],
            "mutation": {"issue_ids": [], "unified_diff": _DIFF},
        }
        application = {
            "proposal": proposal,
            "human_gate": {
                "proposal_digest": proposal_digest(operation, proposal),
                "final_digest": final_digest(operation, final),
                "issue_ids": ["e2-2"],
                "actor": "human",
                "recorded_at": "now",
                "approves_full_mutation": True,
            },
            "final": final,
        }
        assert any(
            "final.mutation.issue_ids" in error
            for error in validate_remediation_application(operation, application)
        )

    def test_non_mutating_decision_forbids_mutation(self):
        application = _mixed_application()
        application["final"]["resolutions"][1]["decision"] = "accept-divergence"
        application["human_gate"]["final_digest"] = final_digest(
            _operation(mixed=True),
            application["final"],
        )
        assert any(
            "final.mutation.issue_ids" in error
            for error in validate_remediation_application(
                _operation(mixed=True),
                application,
            )
        )

    def test_submission_digest_covers_complete_application_canonically(self):
        application = _direct_application()
        operation = _operation()
        digest = application_submission_digest(operation, application)
        reordered = {
            "final": application["final"],
            "human_gate": application["human_gate"],
            "proposal": application["proposal"],
        }
        assert application_submission_digest(operation, reordered) == digest
        reordered["final"]["resolutions"][0]["resolution"] = "changed"
        assert application_submission_digest(operation, reordered) != digest

    def test_semantic_array_reordering_is_stable_for_equality_and_digest(self):
        operation = _operation(mixed=True)
        operation["handling_modes_by_issue"]["e2-2"] = "direct"
        operation["allowed_decisions_by_issue"]["e2-2"] = ["fix"]
        proposal = prepare_remediation_proposal(
            operation,
            _candidate(mixed=True),
        )["proposal"]
        application = {
            "proposal": copy.deepcopy(proposal),
            "human_gate": None,
            "final": {
                "outcome": "apply",
                "resolutions": [
                    {
                        "issue_id": entry["issue_id"],
                        "decision": entry["proposed_decision"],
                        "resolution": entry["resolution"],
                    }
                    for entry in reversed(proposal["proposals"])
                ],
                "mutation": {
                    **proposal["mutation"],
                    "issue_ids": list(reversed(proposal["mutation"]["issue_ids"])),
                },
            },
        }
        assert validate_remediation_application(operation, application) == []
        canonical = canonicalize_remediation_application(operation, application)
        assert canonical["proposal"]["proposals"] == proposal["proposals"]
        assert canonical["final"]["resolutions"][0]["issue_id"] == "e2-1"
        assert application_submission_digest(
            operation,
            application,
        ) == application_submission_digest(operation, canonical)

    def test_embedded_proposal_is_canonicalized_before_receipt_validation(self):
        operation = _operation(mixed=True)
        application = _mixed_application()
        application["proposal"]["proposals"].reverse()
        application["proposal"]["mutation"]["issue_ids"].reverse()
        application["final"]["resolutions"].reverse()
        application["final"]["mutation"]["issue_ids"].reverse()
        application["human_gate"]["proposal_digest"] = proposal_digest(
            operation,
            application["proposal"],
        )
        application["human_gate"]["final_digest"] = final_digest(
            operation,
            application["final"],
        )
        assert validate_remediation_application(operation, application) == []


class TestAbandonApplication:
    def test_abandon_resolves_only_escalated_and_audits_remaining_issues(self):
        proposal = _prepared(mixed=True)
        final = {
            "outcome": "abandon",
            "resolutions": [{
                "issue_id": "e2-2",
                "decision": "escalate",
                "resolution": "requires upstream decision",
            }],
            "proposals": [copy.deepcopy(proposal["proposals"][0])],
            "mutation": None,
        }
        application = {
            "proposal": proposal,
            "human_gate": {
                "proposal_digest": proposal_digest(
                    _operation(mixed=True),
                    proposal,
                ),
                "final_digest": final_digest(_operation(mixed=True), final),
                "issue_ids": ["e2-2"],
                "actor": "human",
                "recorded_at": "now",
                "approves_full_mutation": False,
            },
            "final": final,
        }
        assert validate_remediation_application(
            _operation(mixed=True),
            application,
        ) == []

    def test_abandon_requires_disjoint_full_coverage_and_null_mutation(self):
        application = _mixed_application()
        application["final"] = {
            "outcome": "abandon",
            "resolutions": [{
                "issue_id": "e2-2",
                "decision": "escalate",
                "resolution": "blocked",
            }],
            "proposals": [],
            "mutation": copy.deepcopy(application["proposal"]["mutation"]),
        }
        application["human_gate"]["final_digest"] = final_digest(
            _operation(mixed=True),
            application["final"],
        )
        errors = validate_remediation_application(_operation(mixed=True), application)
        assert any("exactly cover required_issue_ids" in error for error in errors)
        assert any("abandon mutation must be null" in error for error in errors)

    def test_apply_and_abandon_fields_are_discriminated(self):
        application = _direct_application()
        application["final"]["proposals"] = []
        assert any(
            "apply final has invalid fields" in error
            for error in validate_remediation_application(_operation(), application)
        )
