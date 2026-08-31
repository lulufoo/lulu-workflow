"""Review paths and post-probe contracts for Eval."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import eval_control as ec
import session_binding

_ROOT_CAUSES = frozenset({
    "WO-MISS",
    "WO-ERROR",
    "SOT-DEFECT",
    "UNRESOLVABLE",
    "DECISION-REQUIRED",
})
_ARTIFACT_ROOT_CAUSES = frozenset({"WO-MISS", "WO-ERROR"})
_HANDLING_POLICIES = frozenset({"class-default", "human-first"})
_HANDLING_MODES = frozenset({"direct", "human-gated"})


def handling_mode_for_issue(root_cause: str, handling_policy: str) -> str:
    """Map classification and pinned policy to Control-owned handling mode."""
    cause = root_cause.upper()
    if cause not in _ROOT_CAUSES:
        raise ValueError(f"invalid root_cause: {root_cause!r}")
    if handling_policy not in _HANDLING_POLICIES:
        raise ValueError(f"invalid handling_policy: {handling_policy!r}")
    if handling_policy == "human-first" or cause not in _ARTIFACT_ROOT_CAUSES:
        return "human-gated"
    return "direct"


def allowed_decisions_for_issue(
    root_cause: str,
    handling_mode: str,
) -> list[str]:
    """Return the exact decisions authorized by one immutable issue context."""
    cause = root_cause.upper()
    if cause not in _ROOT_CAUSES:
        raise ValueError(f"invalid root_cause: {root_cause!r}")
    if handling_mode not in _HANDLING_MODES:
        raise ValueError(f"invalid handling_mode: {handling_mode!r}")
    if handling_mode == "direct":
        if cause not in _ARTIFACT_ROOT_CAUSES:
            raise ValueError(f"{cause} cannot use direct handling")
        return ["fix"]
    if cause in _ARTIFACT_ROOT_CAUSES:
        return ["fix", "accept-divergence", "escalate"]
    if cause == "DECISION-REQUIRED":
        return ["select", "allow-multiple", "escalate"]
    return ["escalate"]


def validate_review_against_probe_record(
    rows: list[dict[str, str]],
    probe_record: dict[str, Any],
) -> list[dict[str, Any]]:
    """Fail closed if mutable Review identity/classification diverges from Probe."""
    if (
        probe_record.get("operation_kind") != "probe"
        or probe_record.get("phase") != "committed"
    ):
        raise ValueError("Review requires a committed probe operation")
    findings = probe_record.get("canonical_findings")
    if not isinstance(findings, list) or any(
        not isinstance(finding, dict) for finding in findings
    ):
        raise ValueError("committed probe canonical_findings are invalid")
    expected_by_id = {
        str(finding.get("id", "")): finding
        for finding in findings
    }
    actual_by_id = {str(row.get("id", "")): row for row in rows}
    if (
        len(expected_by_id) != len(findings)
        or len(actual_by_id) != len(rows)
        or set(actual_by_id) != set(expected_by_id)
    ):
        raise ValueError("Review finding identity does not match canonical_findings")
    for issue_id, expected in expected_by_id.items():
        actual = actual_by_id[issue_id]
        for field in ("root_cause", "handling_mode"):
            if actual.get(field) != expected.get(field):
                raise ValueError(
                    f"Review {field} mismatch for issue {issue_id!r}",
                )
    return [dict(finding) for finding in findings]


def canonical_probe_findings_from_reviews(
    rows_by_dimension: dict[str, list[dict[str, str]]],
    operation_records: list[dict[str, Any]],
    *,
    expected_dimensions: list[str],
) -> list[dict[str, Any]]:
    """Validate every Review against Probe SSOT and return canonical findings."""
    probe_by_dimension = {
        str(record.get("dimension_id")): record
        for record in operation_records
        if record.get("operation_kind") == "probe"
        and record.get("phase") == "committed"
    }
    if (
        set(rows_by_dimension) != set(expected_dimensions)
        or not set(expected_dimensions) <= set(probe_by_dimension)
    ):
        raise ValueError("missing current-round Review or committed probe operation")
    result: list[dict[str, Any]] = []
    for dimension_id in expected_dimensions:
        findings = validate_review_against_probe_record(
            rows_by_dimension[dimension_id],
            probe_by_dimension[dimension_id],
        )
        result.extend(
            {**finding, "dimension": dimension_id}
            for finding in findings
        )
    return result


def validate_review_completion(
    *,
    rows: list[dict[str, str]],
    dimension_id: str,
    remediation_records: list[dict[str, Any]],
    review_digest: str,
) -> bool:
    """Authorize completion only from empty Probe output or committed remediation."""
    if not rows:
        return True
    if any(row.get("status", "").lower() != "resolved" for row in rows):
        raise ValueError(f"pending findings remain for {dimension_id!r}")
    committed = [
        record
        for record in remediation_records
        if record.get("operation_kind") == "remediation"
        and record.get("dimension_id") == dimension_id
        and record.get("phase") == "committed"
    ]
    if not committed:
        raise ValueError(
            f"resolved Review for {dimension_id!r} lacks committed remediation",
        )
    if not any(
        record.get("review_after_digest") == review_digest
        for record in committed
    ):
        raise ValueError(
            f"Review review_after_digest mismatch for {dimension_id!r}",
        )
    return True


def _review_path_for_dim(
    eval_dir: Path,
    *,
    cycle_id: str,
    state: dict[str, str],
    paths: dict[str, str],
    evaluate_round: int,
    dim: str,
    project_root: Path,
) -> Path:
    expanded = session_binding._expanded_corpus(
        cycle_id,
        state,
        paths,
        evaluate_round,
        project_root=project_root,
    )
    canonical = ec.resolve_dim_id(expanded, dim)
    for item in expanded["dimensions"]:
        if item["id"] == canonical:
            return eval_dir / item["review"]["output_path"]
    raise ValueError(f"unknown dimension: {dim!r}")


def _review_path_from_context(
    cycle_id: str,
    project_root: Path,
    *,
    state: dict[str, str],
    evaluate_round: int,
    active_doc: int,
    dim: str,
) -> Path:
    es_path = session_binding._evaluate_state_path(cycle_id, project_root)
    eval_dir = session_binding._eval_dir(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    paths = session_binding._eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    return _review_path_for_dim(
        eval_dir,
        cycle_id=cycle_id,
        state=state,
        paths=paths,
        evaluate_round=evaluate_round,
        dim=dim,
        project_root=project_root,
    )
