#!/usr/bin/env python3
"""Pure validation and digest helpers for unified remediation payloads."""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

_PROPOSAL_FIELDS = frozenset({
    "round_token",
    "operation_token",
    "target_base_digest",
    "review_base_digest",
    "proposals",
    "mutation",
})
_PROPOSAL_ENTRY_FIELDS = frozenset({
    "issue_id",
    "proposed_decision",
    "resolution",
})
_RESOLUTION_FIELDS = frozenset({"issue_id", "decision", "resolution"})
_MUTATION_FIELDS = frozenset({"issue_ids", "unified_diff"})
_HUMAN_GATE_FIELDS = frozenset({
    "proposal_digest",
    "final_digest",
    "issue_ids",
    "actor",
    "recorded_at",
    "approves_full_mutation",
})
_APPLICATION_FIELDS = frozenset({"proposal", "human_gate", "final"})
_APPLY_FINAL_FIELDS = frozenset({"outcome", "resolutions", "mutation"})
_ABANDON_FINAL_FIELDS = frozenset({
    "outcome",
    "resolutions",
    "proposals",
    "mutation",
})
_MUTATION_REQUIRED = frozenset({"fix", "select", "allow-multiple"})
_MUTATION_FORBIDDEN = frozenset({"accept-divergence", "escalate"})


def canonical_digest(payload: Any) -> str:
    """Return the SHA-256 digest of canonical JSON."""
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _issue_order(operation: dict[str, Any]) -> dict[str, int]:
    return {
        issue_id: index
        for index, issue_id in enumerate(operation.get("required_issue_ids", []))
    }


def _sort_issue_entries(
    entries: Any,
    order: dict[str, int],
) -> Any:
    if not isinstance(entries, list):
        return entries
    return sorted(
        copy.deepcopy(entries),
        key=lambda entry: (
            order.get(str(entry.get("issue_id", "")), len(order))
            if isinstance(entry, dict)
            else len(order)
        ),
    )


def _sort_issue_ids(issue_ids: Any, order: dict[str, int]) -> Any:
    if not isinstance(issue_ids, list):
        return issue_ids
    return sorted(
        copy.deepcopy(issue_ids),
        key=lambda issue_id: order.get(str(issue_id), len(order)),
    )


def canonicalize_remediation_proposal(
    operation: dict[str, Any],
    proposal: dict[str, Any],
) -> dict[str, Any]:
    """Normalize every proposal issue array by required_issue_ids order."""
    canonical = copy.deepcopy(proposal)
    order = _issue_order(operation)
    canonical["proposals"] = _sort_issue_entries(
        canonical.get("proposals"),
        order,
    )
    mutation = canonical.get("mutation")
    if isinstance(mutation, dict):
        mutation["issue_ids"] = _sort_issue_ids(
            mutation.get("issue_ids"),
            order,
        )
    return canonical


def _canonicalize_final(
    operation: dict[str, Any],
    final: dict[str, Any],
) -> dict[str, Any]:
    canonical = copy.deepcopy(final)
    order = _issue_order(operation)
    for field in ("resolutions", "proposals"):
        if field in canonical:
            canonical[field] = _sort_issue_entries(canonical.get(field), order)
    mutation = canonical.get("mutation")
    if isinstance(mutation, dict):
        mutation["issue_ids"] = _sort_issue_ids(
            mutation.get("issue_ids"),
            order,
        )
    return canonical


def final_digest(
    operation: dict[str, Any],
    final: dict[str, Any],
) -> str:
    """Digest final after canonical issue-array normalization."""
    return canonical_digest(_canonicalize_final(operation, final))


def proposal_digest(
    operation: dict[str, Any],
    proposal: dict[str, Any],
) -> str:
    """Digest proposal after canonical issue-array normalization."""
    return canonical_digest(
        canonicalize_remediation_proposal(operation, proposal),
    )


def canonicalize_remediation_application(
    operation: dict[str, Any],
    application: dict[str, Any],
) -> dict[str, Any]:
    """Normalize all issue-bearing arrays in a complete application."""
    canonical = copy.deepcopy(application)
    if isinstance(canonical.get("proposal"), dict):
        canonical["proposal"] = canonicalize_remediation_proposal(
            operation,
            canonical["proposal"],
        )
    if isinstance(canonical.get("final"), dict):
        canonical["final"] = _canonicalize_final(
            operation,
            canonical["final"],
        )
    human_gate = canonical.get("human_gate")
    if isinstance(human_gate, dict):
        human_gate["issue_ids"] = _sort_issue_ids(
            human_gate.get("issue_ids"),
            _issue_order(operation),
        )
    return canonical


def application_submission_digest(
    operation: dict[str, Any],
    application: dict[str, Any],
) -> str:
    """Digest a complete canonical RemediationApplication payload."""
    return canonical_digest(
        canonicalize_remediation_application(operation, application),
    )


def _entries_by_issue(
    entries: Any,
    *,
    decision_field: str,
    expected_fields: frozenset[str],
    label: str,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    if not isinstance(entries, list):
        return {}, [f"{label} must be an array"]
    indexed: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        if set(entry) != expected_fields:
            errors.append(f"{label}[{index}] has invalid fields")
        issue_id = entry.get("issue_id")
        if not isinstance(issue_id, str) or not issue_id:
            errors.append(f"{label}[{index}].issue_id must be non-empty")
            continue
        if issue_id in indexed:
            errors.append(f"{label} contains duplicate issue_id {issue_id!r}")
        indexed[issue_id] = entry
        decision = entry.get(decision_field)
        if not isinstance(decision, str) or not decision:
            errors.append(f"{label}[{index}].{decision_field} must be non-empty")
        resolution = entry.get("resolution")
        if not isinstance(resolution, str) or not resolution.strip():
            errors.append(f"{label}[{index}].resolution must be non-empty")
    return indexed, errors


def _validate_mutation(
    mutation: Any,
    required_mutation_ids: set[str],
    *,
    label: str,
) -> list[str]:
    if not required_mutation_ids:
        return [] if mutation is None else [f"{label} must be null"]
    if not isinstance(mutation, dict):
        return [f"{label} is required"]
    errors: list[str] = []
    if set(mutation) != _MUTATION_FIELDS:
        errors.append(f"{label} has invalid fields")
    issue_ids = mutation.get("issue_ids")
    if (
        not isinstance(issue_ids, list)
        or any(not isinstance(issue_id, str) or not issue_id for issue_id in issue_ids)
        or len(issue_ids) != len(set(issue_ids))
        or set(issue_ids) != required_mutation_ids
    ):
        errors.append(
            f"{label}.issue_ids must uniquely equal all mutation-required issues",
        )
    unified_diff = mutation.get("unified_diff")
    if not isinstance(unified_diff, str) or not unified_diff.strip():
        errors.append(f"{label}.unified_diff must be non-empty")
    return errors


def validate_remediation_proposal(
    operation: dict[str, Any],
    proposal: Any,
) -> list[str]:
    """Validate one proposal against its immutable operation context."""
    if not isinstance(proposal, dict):
        return ["proposal must be an object"]
    errors: list[str] = []
    if set(proposal) != _PROPOSAL_FIELDS:
        errors.append("proposal has invalid fields")

    for field in (
        "round_token",
        "operation_token",
        "target_base_digest",
        "review_base_digest",
    ):
        if proposal.get(field) != operation.get(field):
            errors.append(f"proposal {field} does not match operation")

    required_ids = operation.get("required_issue_ids")
    if (
        not isinstance(required_ids, list)
        or not required_ids
        or len(required_ids) != len(set(required_ids))
    ):
        return [*errors, "operation required_issue_ids is invalid"]
    required = set(required_ids)

    entries, entry_errors = _entries_by_issue(
        proposal.get("proposals"),
        decision_field="proposed_decision",
        expected_fields=_PROPOSAL_ENTRY_FIELDS,
        label="proposals",
    )
    errors.extend(entry_errors)
    if set(entries) != required:
        errors.append("proposals must exactly cover required_issue_ids")

    modes = operation.get("handling_modes_by_issue", {})
    allowed = operation.get("allowed_decisions_by_issue", {})
    mutation_ids: set[str] = set()
    for issue_id, entry in entries.items():
        decision = entry.get("proposed_decision")
        allowed_decisions = allowed.get(issue_id, [])
        if decision not in allowed_decisions:
            errors.append(
                f"issue {issue_id!r} proposed_decision is not allowed",
            )
        if modes.get(issue_id) == "direct":
            if allowed_decisions != ["fix"] or decision != "fix":
                errors.append(
                    f"direct issue {issue_id!r} must use pre-authorized fix",
                )
        if decision in _MUTATION_REQUIRED:
            mutation_ids.add(issue_id)
        elif decision not in _MUTATION_FORBIDDEN:
            errors.append(f"issue {issue_id!r} has unknown mutation mapping")

    errors.extend(
        _validate_mutation(
            proposal.get("mutation"),
            mutation_ids,
            label="mutation",
        ),
    )
    return errors


def prepare_remediation_proposal(
    operation: dict[str, Any],
    candidate: dict[str, Any],
) -> dict[str, Any]:
    """Validate and canonicalize a proposal without mutating either input."""
    if operation.get("phase") != "context-open":
        raise ValueError("prepare-remediation requires context-open operation")
    errors = validate_remediation_proposal(operation, candidate)
    if errors:
        raise ValueError(f"remediation proposal invalid: {'; '.join(errors)}")
    canonical = canonicalize_remediation_proposal(operation, candidate)
    return {
        "proposal": canonical,
        "proposal_digest": proposal_digest(operation, canonical),
    }


def _expected_apply_from_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "outcome": "apply",
        "resolutions": [
            {
                "issue_id": entry["issue_id"],
                "decision": entry["proposed_decision"],
                "resolution": entry["resolution"],
            }
            for entry in proposal["proposals"]
        ],
        "mutation": copy.deepcopy(proposal["mutation"]),
    }


def _validate_human_gate(
    operation: dict[str, Any],
    proposal: dict[str, Any],
    final: dict[str, Any],
    human_gate: Any,
) -> list[str]:
    human_issue_ids = [
        issue_id
        for issue_id in operation["required_issue_ids"]
        if operation["handling_modes_by_issue"].get(issue_id) == "human-gated"
    ]
    if not human_issue_ids:
        return [] if human_gate is None else ["all-direct operation requires null human_gate"]
    if not isinstance(human_gate, dict):
        return ["human_gate is required for human-gated issues"]

    errors: list[str] = []
    if set(human_gate) != _HUMAN_GATE_FIELDS:
        errors.append("human_gate has invalid fields")
    if human_gate.get("proposal_digest") != proposal_digest(operation, proposal):
        errors.append("human_gate proposal_digest mismatch")
    if human_gate.get("final_digest") != final_digest(operation, final):
        errors.append("human_gate final_digest mismatch")
    if human_gate.get("issue_ids") != human_issue_ids:
        errors.append("human_gate issue_ids must list all human-gated issues")
    for field in ("actor", "recorded_at"):
        if not isinstance(human_gate.get(field), str) or not human_gate[field].strip():
            errors.append(f"human_gate {field} must be non-empty")
    if not isinstance(human_gate.get("approves_full_mutation"), bool):
        errors.append("human_gate approves_full_mutation must be boolean")
    if (
        final.get("outcome") == "apply"
        and _canonicalize_final(operation, final).get("mutation")
        != canonicalize_remediation_proposal(operation, proposal).get("mutation")
        and human_gate.get("approves_full_mutation") is not True
    ):
        errors.append(
            "human_gate approves_full_mutation must be true when final mutation changes",
        )
    return errors


def _validate_apply_final(
    operation: dict[str, Any],
    proposal: dict[str, Any],
    final: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if set(final) != _APPLY_FINAL_FIELDS:
        errors.append("apply final has invalid fields")
    resolutions, resolution_errors = _entries_by_issue(
        final.get("resolutions"),
        decision_field="decision",
        expected_fields=_RESOLUTION_FIELDS,
        label="final.resolutions",
    )
    errors.extend(resolution_errors)
    required = set(operation["required_issue_ids"])
    if set(resolutions) != required:
        errors.append("final.resolutions must exactly cover required_issue_ids")

    proposal_entries = {
        entry["issue_id"]: entry for entry in proposal.get("proposals", [])
    }
    mutation_ids: set[str] = set()
    for issue_id, resolution in resolutions.items():
        decision = resolution.get("decision")
        if decision == "escalate":
            errors.append("apply outcome forbids escalate")
        if decision not in operation["allowed_decisions_by_issue"].get(issue_id, []):
            errors.append(f"issue {issue_id!r} final decision is not allowed")
        if operation["handling_modes_by_issue"].get(issue_id) == "direct":
            proposed = proposal_entries.get(issue_id, {})
            if (
                decision != proposed.get("proposed_decision")
                or resolution.get("resolution") != proposed.get("resolution")
            ):
                errors.append(
                    f"direct issue {issue_id!r} decision and resolution are immutable",
                )
        if decision in _MUTATION_REQUIRED:
            mutation_ids.add(issue_id)
        elif decision not in _MUTATION_FORBIDDEN:
            errors.append(f"issue {issue_id!r} has unknown mutation mapping")

    errors.extend(
        _validate_mutation(
            final.get("mutation"),
            mutation_ids,
            label="final.mutation",
        ),
    )
    if not any(
        mode == "human-gated"
        for mode in operation["handling_modes_by_issue"].values()
    ) and _canonicalize_final(
        operation,
        final,
    ) != _expected_apply_from_proposal(
        canonicalize_remediation_proposal(operation, proposal),
    ):
        errors.append("all-direct final must equal proposal")
    return errors


def _validate_abandon_final(
    operation: dict[str, Any],
    proposal: dict[str, Any],
    final: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if set(final) != _ABANDON_FINAL_FIELDS:
        errors.append("abandon final has invalid fields")
    resolutions, resolution_errors = _entries_by_issue(
        final.get("resolutions"),
        decision_field="decision",
        expected_fields=_RESOLUTION_FIELDS,
        label="final.resolutions",
    )
    errors.extend(resolution_errors)
    audit_proposals, proposal_errors = _entries_by_issue(
        final.get("proposals"),
        decision_field="proposed_decision",
        expected_fields=_PROPOSAL_ENTRY_FIELDS,
        label="final.proposals",
    )
    errors.extend(proposal_errors)

    required = set(operation["required_issue_ids"])
    resolved_ids = set(resolutions)
    proposal_ids = set(audit_proposals)
    if (
        not resolved_ids
        or resolved_ids & proposal_ids
        or resolved_ids | proposal_ids != required
    ):
        errors.append(
            "abandon resolutions and proposals must be disjoint and exactly cover required_issue_ids",
        )
    for issue_id, resolution in resolutions.items():
        if (
            resolution.get("decision") != "escalate"
            or operation["handling_modes_by_issue"].get(issue_id) != "human-gated"
            or "escalate"
            not in operation["allowed_decisions_by_issue"].get(issue_id, [])
        ):
            errors.append(
                f"abandon resolution {issue_id!r} must be authorized human-gated escalate",
            )
    original = {
        entry["issue_id"]: entry for entry in proposal.get("proposals", [])
    }
    for issue_id, audit_entry in audit_proposals.items():
        if audit_entry != original.get(issue_id):
            errors.append(
                f"abandon audit proposal {issue_id!r} must match embedded proposal",
            )
    if final.get("mutation") is not None:
        errors.append("abandon mutation must be null")
    return errors


def validate_remediation_application(
    operation: dict[str, Any],
    application: Any,
) -> list[str]:
    """Validate a complete application and revalidate its embedded proposal."""
    if not isinstance(application, dict):
        return ["application must be an object"]
    errors: list[str] = []
    if set(application) != _APPLICATION_FIELDS:
        errors.append("application has invalid fields")

    canonical_application = canonicalize_remediation_application(
        operation,
        application,
    )
    proposal = canonical_application.get("proposal")
    proposal_errors = validate_remediation_proposal(operation, proposal)
    errors.extend(
        f"embedded proposal invalid: {error}" for error in proposal_errors
    )
    if not isinstance(proposal, dict):
        return errors
    final = canonical_application.get("final")
    if not isinstance(final, dict):
        return [*errors, "final must be an object"]

    outcome = final.get("outcome")
    if outcome == "apply":
        errors.extend(_validate_apply_final(operation, proposal, final))
    elif outcome == "abandon":
        errors.extend(_validate_abandon_final(operation, proposal, final))
    else:
        errors.append(f"invalid final outcome: {outcome!r}")

    errors.extend(
        _validate_human_gate(
            operation,
            proposal,
            final,
            canonical_application.get("human_gate"),
        ),
    )
    return errors
