#!/usr/bin/env python3
"""Eval control for lulu-dev-workflow eval domain.

Owns mechanical writes to evaluate-state.md. Workflow-specific paths and state
transitions go through an injected WorkflowAdapter, loaded per-profile by
eval_entry.py (caller-supplied adapter config: flat Adapter or decorator envelope)
loading, mirrors start.py's StartAdapter loading).

Invoke via eval_entry.py with caller-supplied adapter config
(e.g. `--adapter-config-file <json>`). Do not run this module as __main__.

Subcommands:
    init-round                  Initialize evaluate-state.md (internal; session_control)
    begin-eval-round            Enter focus evaluating (session stays Working) or next round
    begin-dimension             Mark dimension probing and return eval-runner inputs
    read-b-snapshot             Read token-authorized EvalTarget B content
    read-evidence-snapshot      Read token-authorized dynamic SoT evidence
    submit-probe-findings       Validate and publish token-scoped probe findings
    check-dimension             Read-only verify dimension probed or complete after eval-runner
    begin-remediation           Enter remediation and return dispatch or skip
    begin-dimension-remediation Create/resume one unified remediation context
    cancel-remediation          Cancel context-open operation and release target lease
    prepare-remediation         Read-only validation of a RemediationProposal
    apply-remediation           Validate and commit a RemediationApplication
    check-dimension-remediation Rebuild one Dimension projection
    remediation-complete        Complete a full-remediation round
    complete-probe-only         Complete a probe-only round with pending findings
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
from datetime import date
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable

_EVAL_LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(_EVAL_LIB))

from review_io import (  # noqa: E402
    count_resolved,
    parse_review_file,
    split_table_row,
)
from review_schema import (  # noqa: E402
    render_review_header,
    validate_review_content,
    validate_review_file,
)
from corpus_schema import (  # noqa: E402
    expand_corpus,
    resolve_dim_id,
)
from evaluate_state_schema import (  # noqa: E402
    is_v8_state,
    load_evaluate_state,
    parse_frontmatter_fields,
    parse_dimension_status,
    parse_handling_policy,
    parse_issue_counts,
    parse_skip_reason,
    patch_issue_count,
    save_evaluate_state,
)
from corpus_snapshot import (  # noqa: E402
    SNAPSHOT_REF,
    load_materialized_corpus,
    snapshot_dir,
)
from eval_admission import (  # noqa: E402
    finalize_admission,
    load_journal,
    load_prepared_admission_corpus,
    mark_transitioned,
    publish_prepared_snapshot,
    record_handoff_lease,
    recover_admission,
    this_attempt_is_committed,
)

from evaluate_state_ops import (  # noqa: E402
    build_initial_evaluate_state_for_corpus,
    dimension_status_legacy_map,
    dispatch_legacy_for_corpus,
    merge_current_dimension,
)
from workflow_adapter import WorkflowAdapter  # noqa: E402
from eval_handoff_schema import (  # noqa: E402
    build_artifact_manifest_v2,
    validate_eval_handoff_v2,
)
from eval_operation_context import (  # noqa: E402
    discard_operation_context,
    issue_probe_context,
    issue_remediation_context,
    read_evidence_snapshot,
    read_target_snapshot,
)
from eval_operation_record_schema import (  # noqa: E402
    advance_operation_record,
    cancel_operation_record,
    get_operation_record,
    load_operation_records,
)
from remediation_schema import (  # noqa: E402
    application_submission_digest,
    canonicalize_remediation_application,
    prepare_remediation_proposal,
    validate_remediation_application,
)
from unified_diff import apply_unified_diff  # noqa: E402

_ADAPTER_CTX: ContextVar[WorkflowAdapter | None] = ContextVar("workflow_adapter", default=None)
_WORKFLOW_ID_CTX: ContextVar[str | None] = ContextVar("workflow_id", default=None)
_HANDOFF_CTX: ContextVar[dict[str, Any] | None] = ContextVar("eval_handoff", default=None)
_CRASH_AFTER_PHASE: ContextVar[str | None] = ContextVar("apply_crash_after_phase", default=None)


def _adapter() -> WorkflowAdapter:
    adapter = _ADAPTER_CTX.get()
    if adapter is None:
        raise RuntimeError(
            "WorkflowAdapter not set; invoke via eval_entry.py "
            "(profile-driven adapter loading)",
        )
    return adapter


def _workflow_id() -> str:
    workflow_id = _WORKFLOW_ID_CTX.get()
    if not workflow_id:
        raise RuntimeError(
            "WORKFLOW_ID not set; invoke via eval_entry.py "
            "(--adapter-config-file / --adapter-config)",
        )
    return workflow_id


def _handoff() -> dict[str, Any] | None:
    return _HANDOFF_CTX.get()


def _handoff_context() -> dict[str, Any] | None:
    handoff = _handoff()
    if not handoff:
        return None
    context = handoff.get("context")
    return context if isinstance(context, dict) else None


def _refresh_handoff(
    cycle_id: str,
    project_root: Path,
    *,
    require_evaluating: bool = True,
) -> dict[str, Any]:
    """Request a fresh workflow handoff and store it in the context var."""
    handoff = _adapter().request_eval_handoff(
        cycle_id,
        project_root,
        require_evaluating=require_evaluating,
    )
    if not isinstance(handoff, dict):
        raise ValueError("workflow EvalHandoff missing")
    errors = validate_eval_handoff_v2(handoff)
    if errors:
        raise ValueError("; ".join(errors))
    _HANDOFF_CTX.set(handoff)
    return handoff


def _upstream_baseline_ref(cycle_id: str, project_root: Path) -> str:
    """Upstream baseline from Compose handoff policy_context when present."""
    context = _handoff_context()
    if context:
        policy = context.get("policy_context") or {}
        ref = str(policy.get("upstream_baseline_ref", "")).strip()
        if ref:
            return ref
    return _adapter().session_context(cycle_id, project_root).upstream_baseline_ref


def _load_corpus(cycle_id: str, project_root: Path):
    """Load the pinned round snapshot, or resolve only before admission."""
    es_path = _evaluate_state_path(cycle_id, project_root)
    if not es_path.is_file():
        return _adapter().resolve_eval_corpus(cycle_id, project_root)
    fields = parse_frontmatter_fields(es_path.read_text(encoding="utf-8"))
    digest = str(fields.get("corpus_digest") or "").strip()
    ref = str(fields.get("corpus_snapshot_ref") or "").strip()
    if not digest or not ref:
        raise ValueError(
            "incompatible_round: evaluate-state missing corpus snapshot",
        )
    evaluate_dir = _evaluate_dir_for_snapshot(cycle_id, project_root, fields)
    return load_materialized_corpus(
        snapshot_dir(evaluate_dir),
        expected_digest=digest,
    )


def _evaluate_dir_for_snapshot(
    cycle_id: str,
    project_root: Path,
    fields: dict[str, str],
) -> Path:
    context = _handoff_context() or {}
    raw = context.get("evaluate_dir")
    if raw:
        return Path(str(raw))
    try:
        evaluate_round = int(fields.get("evaluate_round") or 1)
    except ValueError:
        evaluate_round = 1
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=_adapter().session_context(cycle_id, project_root).active_doc,
        evaluate_round=evaluate_round,
        es_path=_evaluate_state_path(cycle_id, project_root),
    )
    return Path(str(paths["evaluate_dir"]))


def _dispatch_dim_allowed(cycle_id: str, project_root: Path, dim: str) -> bool:
    """Return True when dim is a legacy alias or canonical id in session corpus."""
    try:
        corpus = _load_corpus(cycle_id, project_root)
        resolve_dim_id(corpus, dim)
    except ValueError:
        return False
    legacy = dispatch_list(cycle_id, project_root)
    canonical = _dispatch_canonical(cycle_id, project_root)
    return dim in legacy or dim in canonical


def dispatch_list(cycle_id: str, project_root: Path) -> list[str]:
    """Return legacy Eval dimension dispatch (e2/e3/e4) for Eval orchestration."""
    return dispatch_legacy_for_corpus(_load_corpus(cycle_id, project_root))


def _dispatch_canonical(cycle_id: str, project_root: Path) -> list[str]:
    """Return canonical dimension ids from session EvalCorpus."""
    from evaluate_state_ops import dispatch_dims_for_corpus

    return dispatch_dims_for_corpus(_load_corpus(cycle_id, project_root))


def _paths_from_handoff() -> dict[str, str] | None:
    context = _handoff_context()
    if not context:
        return None
    bindings = context.get("bindings")
    if not isinstance(bindings, dict):
        raise ValueError("EvalHandoff bindings missing")
    return {
        "eval_target_path": str(bindings.get("eval_target_path", "")),
        "evaluate_state": str(context["evaluate_state_path"]),
        "evaluate_dir": str(context["evaluate_dir"]),
        "write_staging_dir": str(context["write_staging_dir"]),
        "lease_id": str(context["lease_id"]),
        "session_key": str(context["session_key"]),
    }


def _eval_paths(
    cycle_id: str,
    project_root: Path,
    *,
    active_doc: int,
    evaluate_round: int,
    es_path: Path | None = None,
) -> dict[str, str]:
    from_handoff = _paths_from_handoff()
    if from_handoff is not None:
        return from_handoff
    if es_path is None:
        es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
    return _adapter().eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )


def _eval_dir(
    cycle_id: str,
    project_root: Path,
    *,
    active_doc: int,
    evaluate_round: int,
    es_path: Path | None = None,
) -> Path:
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    return Path(paths["evaluate_dir"])


def _evaluate_state_path(cycle_id: str, project_root: Path) -> Path:
    context = _handoff_context()
    if context:
        return Path(str(context["evaluate_state_path"]))
    return _adapter().resolve_evaluate_state_path(cycle_id, project_root)


def _commit_staged_evaluate_state(
    cycle_id: str,
    project_root: Path,
    *,
    patch: dict[str, str] | None = None,
    update: Callable[[dict[str, str]], dict[str, str]] | None = None,
    state: dict[str, str] | None = None,
    state_content: str | None = None,
    set_phase_evaluating: bool = False,
    previous_done_required: bool = False,
) -> str | None:
    """Stage a full evaluate state and publish it through the workflow adapter."""
    paths = _paths_from_handoff()
    if paths is None:
        _refresh_handoff(
            cycle_id,
            project_root,
            require_evaluating=not set_phase_evaluating,
        )
        paths = _paths_from_handoff()
    if paths is None:
        raise ValueError("EvalHandoff paths missing")

    formal_state_path = Path(paths["evaluate_state"])
    lock_path = formal_state_path.with_suffix(formal_state_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if state_content is not None:
                if state is not None or patch is not None or update is not None:
                    raise ValueError(
                        "state_content cannot be combined with state, patch, or update",
                    )
                next_state = None
            elif state is not None:
                if patch is not None or update is not None:
                    raise ValueError("state cannot be combined with patch or update")
                next_state = dict(state)
            else:
                current_state = load_evaluate_state(formal_state_path)
                if update is not None:
                    next_state = update(current_state)
                else:
                    next_state = dict(current_state)
                    next_state.update(patch or {})

            staged_state_path = Path(paths["write_staging_dir"]) / "evaluate-state.md"
            if state_content is not None:
                _atomic_write_text(staged_state_path, state_content)
                load_evaluate_state(staged_state_path)
            else:
                save_evaluate_state(staged_state_path, next_state, merge=False)
            publish = _adapter().commit_evaluate_state(
                cycle_id,
                project_root,
                staged_state_path=staged_state_path,
                set_phase_evaluating=set_phase_evaluating,
                previous_done_required=previous_done_required,
            )
            if publish.get("ok"):
                return None
            staged_state_path.unlink(missing_ok=True)
            return str(publish.get("error") or "commit-evaluate-state failed")
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


_CMD_INIT_ROUND = "init-round"
_CMD_BEGIN_EVAL_ROUND = "begin-eval-round"
_CMD_BEGIN_DIMENSION = "begin-dimension"
_CMD_READ_B_SNAPSHOT = "read-b-snapshot"
_CMD_READ_EVIDENCE_SNAPSHOT = "read-evidence-snapshot"
_CMD_SUBMIT_PROBE_FINDINGS = "submit-probe-findings"
_CMD_CHECK_DIMENSION = "check-dimension"
_CMD_BEGIN_REMEDIATION = "begin-remediation"
_CMD_BEGIN_DIMENSION_REMEDIATION = "begin-dimension-remediation"
_CMD_CANCEL_REMEDIATION = "cancel-remediation"
_CMD_PREPARE_REMEDIATION = "prepare-remediation"
_CMD_APPLY_REMEDIATION = "apply-remediation"
_CMD_CHECK_DIMENSION_REMEDIATION = "check-dimension-remediation"
_CMD_REMEDIATION_COMPLETE = "remediation-complete"
_CMD_COMPLETE_PROBE_ONLY = "complete-probe-only"

def _review_prefix_from_corpus(corpus: dict[str, Any]) -> str:
    """Derive the review file prefix from the corpus output_path template.

    The corpus already encodes the prefix in each dimension's review.output_path,
    e.g. "design-review-e{M}1.md" → prefix "design-review".
    This keeps eval independent of stage-specific naming conventions.
    """
    dims = corpus.get("dimensions", [])
    if dims:
        output_path = dims[0].get("review", {}).get("output_path", "")
        m = re.match(r"^(.+?)-e\{M\}\d+\.md$", output_path)
        if m:
            return m.group(1)
    return ""


_ENTRY_V7_KEYS = (
    "version",
    "corpus_ref",
    "corpus_fingerprint",
    "dimension_dispatch",
    "eval_capability",
    "handling_policy",
)
_EXPECTED_SESSION_STATE = "Working"
_EXPECTED_FOCUS_PHASE = "evaluating"
_VALID_MODES = frozenset({"product", "tech"})
_SEVERITY_RANK = {"critical": 3, "medium": 2, "minor": 1}
_PROBE_PAYLOAD_KEYS = frozenset({"dimension_token", "findings"})
_FINDING_REQUIRED_KEYS = frozenset(
    {"id", "root_cause", "location", "severity", "evidence", "description"},
)
_FINDING_OPTIONAL_KEYS = frozenset({"sot_ref", "realign_gate"})


def _bind_vars(
    cycle_id: str,
    state: dict[str, str],
    paths: dict[str, str],
    evaluate_round: int,
    *,
    project_root: Path,
) -> dict[str, str]:
    bind = {
        "eval_target_path": paths.get("eval_target_path") or paths.get("compose_doc", ""),
        "upstream_baseline_ref": _upstream_baseline_ref(cycle_id, project_root),
        "cycle_type": _adapter().detect_cycle_type(cycle_id),
        "M": str(evaluate_round),
    }
    bind.update(_adapter().corpus_bind_extensions(cycle_id, project_root))
    return bind


def _expanded_corpus(
    cycle_id: str,
    state: dict[str, str],
    paths: dict[str, str],
    evaluate_round: int,
    *,
    project_root: Path,
) -> dict[str, Any]:
    return expand_corpus(
        _load_corpus(cycle_id, project_root),
        _bind_vars(
            cycle_id,
            state,
            paths,
            evaluate_round,
            project_root=project_root,
        ),
    )


def _canonical_dim(cycle_id: str, project_root: Path, dim: str) -> str:
    return resolve_dim_id(_load_corpus(cycle_id, project_root), dim)


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


def _recompute_aggregate_counts(data: dict[str, str]) -> dict[str, str]:
    """Keep v7 aggregate counters equal to their issue-count projection."""
    updated = dict(data)
    counts = parse_issue_counts(updated.get("issue_counts", "{}"))
    updated["total_issues"] = str(sum(item["total"] for item in counts.values()))
    updated["resolved_issues"] = str(
        sum(item["resolved"] for item in counts.values()),
    )
    return updated


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


def validate_live_target_digest(target_path: Path, expected_digest: str) -> None:
    """Reject publication when the live target changed since context capture."""
    actual = hashlib.sha256(target_path.read_bytes()).hexdigest()
    if actual != expected_digest:
        raise ValueError(
            "stale target: live digest does not match operation target_base_digest",
        )


def _success(command: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "command": command}
    payload.update(extra)
    return payload


def _failure(command: str, reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "command": command, "reason": reason}
    payload.update(extra)
    return payload


def _crash_after(phase: str) -> None:
    if _CRASH_AFTER_PHASE.get() == phase:
        raise RuntimeError(f"injected crash after {phase}")


def _content_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _target_path_from_record(record: dict[str, Any]) -> Path:
    raw = record.get("target_path") or record.get("target_lease_key")
    if not isinstance(raw, str) or not raw:
        raise ValueError("operation record missing target path")
    return Path(raw)


def _live_target_digest(
    cycle_id: str,
    project_root: Path,
    target_path: Path,
) -> str:
    adapter = _adapter()
    reader = getattr(adapter, "read_eval_target_digest", None)
    if callable(reader):
        return str(reader(cycle_id, project_root, target_path=target_path))
    return hashlib.sha256(target_path.read_bytes()).hexdigest()


def _review_live_state(review_path: Path, record: dict[str, Any]) -> str:
    if not review_path.is_file():
        return "before" if record.get("review_before_exists") is not True else "unknown"
    digest = _content_digest(review_path.read_text(encoding="utf-8"))
    if record.get("review_before_exists") is True and digest == record.get(
        "review_base_digest",
    ):
        return "before"
    if digest == record.get("review_after_digest"):
        return "after"
    return "unknown"


def _target_live_state(live_digest: str, record: dict[str, Any]) -> str:
    if record.get("target_effect") == "none":
        return "base" if live_digest == record.get("target_base_digest") else "other"
    if live_digest == record.get("target_base_digest"):
        return "before"
    if live_digest == record.get("target_after_digest"):
        return "after"
    return "unknown"


def _render_review_after(
    before_content: str,
    updates: dict[str, tuple[str, str, str]],
) -> str:
    rendered: list[str] = []
    header_seen = False
    for line in before_content.splitlines(keepends=True):
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("|---"):
            rendered.append(line)
            continue
        cells = split_table_row(stripped)
        if not header_seen:
            header_seen = True
            rendered.append(line)
            continue
        issue_id = cells[0] if cells else ""
        if issue_id in updates and len(cells) >= 11:
            status, decision, resolution = updates[issue_id]
            cells[8] = status
            cells[9] = decision
            cells[10] = resolution
            rendered.append("| " + " | ".join(cells) + " |\n")
        else:
            rendered.append(line)
    return "".join(rendered)


def _publish_review_after(review_path: Path, content: str) -> None:
    _atomic_write_review(review_path, content)


def _commit_eval_target(
    cycle_id: str,
    project_root: Path,
    record: dict[str, Any],
    paths: dict[str, str],
) -> None:
    staged = record.get("target_staged_path")
    if not isinstance(staged, str) or not staged:
        raise ValueError("prepared mutation is missing target_staged_path")
    result = _adapter().commit_eval_target(
        cycle_id,
        project_root,
        staged_target_path=Path(staged),
        base_digest=str(record["target_base_digest"]),
        lease_id=str(paths.get("lease_id", "")),
    )
    if not result.get("ok"):
        raise ValueError(str(result.get("error") or "commit_eval_target failed"))


def _advance_phase(
    operations_path: Path,
    record: dict[str, Any],
    phase: str,
) -> dict[str, Any]:
    advanced = advance_operation_record(operations_path, {**record, "phase": phase})
    _crash_after(phase)
    return advanced


def _forward_recover_to_committed(
    cycle_id: str,
    project_root: Path,
    *,
    command: str,
    operations_path: Path,
    record: dict[str, Any],
    paths: dict[str, str],
    review_path: Path,
    evaluate_round: int,
) -> dict[str, Any]:
    """Advance a prepared-or-later operation to committed, or fail closed."""
    review_file = Path(record["review_path"]) if record.get("review_path") else review_path
    target_path = _target_path_from_record(record)
    try:
        live_target = _live_target_digest(cycle_id, project_root, target_path)
    except (OSError, ValueError) as exc:
        return _failure(command, f"repair_required: {exc}")
    review_state = _review_live_state(review_file, record)
    target_state = _target_live_state(live_target, record)
    if review_state == "unknown":
        return _failure(command, "repair_required: live Review digest is unknown")
    if record.get("target_effect") == "none":
        if target_state != "base":
            return _failure(
                command,
                "repair_required: live target is not the verified base digest",
            )
    else:
        if target_state == "unknown":
            return _failure(command, "repair_required: live target digest is unknown")
        if target_state == "before" and review_state == "after":
            return _failure(
                command,
                "repair_required: target before and Review after",
            )

    try:
        if record.get("phase") == "prepared":
            if record.get("target_effect") == "mutation" and target_state == "before":
                _commit_eval_target(cycle_id, project_root, record, paths)
                target_state = "after"
            record = _advance_phase(operations_path, record, "target-applied")
        if record.get("phase") == "target-applied":
            if review_state == "before":
                if record.get("operation_kind") == "probe":
                    publish_error = _publish_probe_review(
                        cycle_id,
                        project_root,
                        paths=paths,
                        evaluate_round=evaluate_round,
                        formal_review_path=review_file,
                        content=str(record["review_after_content"]),
                    )
                    if publish_error is not None:
                        return _failure(command, publish_error)
                else:
                    _publish_review_after(
                        review_file,
                        str(record["review_after_content"]),
                    )
                review_state = "after"
            elif review_state != "after":
                return _failure(
                    command,
                    "repair_required: live Review digest is unknown",
                )
            record = _advance_phase(operations_path, record, "review-applied")
        if record.get("phase") == "review-applied":
            record = advance_operation_record(
                operations_path,
                {**record, "phase": "committed"},
            )
    except ValueError as exc:
        reason = str(exc)
        if reason.startswith("repair_required"):
            return _failure(command, reason)
        return _failure(command, reason)
    return {"ok": True, "record": record}


def _abandoned_failure(
    command: str,
    state: dict[str, str],
    eval_data: dict[str, str],
) -> dict[str, Any] | None:
    if eval_data.get("eval_status") != "abandoned":
        return None
    return _failure(
        command,
        "evaluation was abandoned (eval_status: abandoned).",
        current_state=state["current_state"],
    )


def _validate_evaluate_state_for_session(
    eval_data: dict[str, str],
    cycle_id: str,
    project_root: Path,
) -> str | None:
    """Return error reason when evaluate-state does not match session at entry."""
    if not is_v8_state(eval_data):
        return "incompatible_round: evaluate-state is not v8."
    if eval_data.get("phase") != "evaluate":
        return f"phase is {eval_data.get('phase')!r}, expected 'evaluate'."
    try:
        expected = build_initial_evaluate_state_for_corpus(
            _load_corpus(cycle_id, project_root),
            eval_capability=_eval_capability(),
            cycle_type=_adapter().detect_cycle_type(cycle_id),
        )
    except ValueError as exc:
        return str(exc)
    for key in _ENTRY_V7_KEYS:
        actual = eval_data.get(key)
        exp = expected.get(key)
        if actual != exp:
            return (
                f"{key} is {actual!r}, expected {exp!r} "
                f"for this session."
            )
    expected_dimensions = parse_dimension_status(expected["dimension_status"])
    actual_dimensions = parse_dimension_status(eval_data["dimension_status"])
    if set(actual_dimensions) != set(expected_dimensions):
        return (
            f"dimension_status keys are {sorted(actual_dimensions)!r}, expected "
            f"{sorted(expected_dimensions)!r} for this session."
        )
    return None


def _eval_capability() -> str:
    """Return the capability pinned by handoff, defaulting legacy adapters to full."""
    context = _handoff_context() or {}
    policy_context = context.get("policy_context")
    if isinstance(policy_context, dict):
        capability = policy_context.get("eval_capability")
        if capability in {"full-remediation", "probe-only"}:
            return str(capability)
    capability = context.get("eval_capability")
    if capability in {"full-remediation", "probe-only"}:
        return str(capability)
    return "full-remediation"


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
    expanded = _expanded_corpus(
        cycle_id,
        state,
        paths,
        evaluate_round,
        project_root=project_root,
    )
    canonical = resolve_dim_id(expanded, dim)
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
    es_path = _evaluate_state_path(cycle_id, project_root)
    eval_dir = _eval_dir(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    paths = _eval_paths(
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


def dimension_from_review_path(
    path: Path,
    *,
    cycle_id: str,
    project_root: Path,
) -> str:
    corpus = _load_corpus(cycle_id, project_root)
    prefix = _review_prefix_from_corpus(corpus)
    if not prefix:
        return ""
    review_re = re.compile(rf"{re.escape(prefix)}-e\d+(\d+)\.md$")
    match = review_re.search(path.name)
    if not match:
        return ""
    seq = int(match.group(1))
    for item in corpus["dimensions"]:
        if item["review"]["seq"] == seq:
            return str(item.get("legacy_alias") or item["id"])
    return ""


def collect_review_issues(
    eval_dir: Path,
    *,
    cycle_id: str,
    project_root: Path,
) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[dict[str, str]] = []
    review_paths: list[str] = []
    if not eval_dir.is_dir():
        return issues, review_paths

    corpus = _load_corpus(cycle_id, project_root)
    prefix = _review_prefix_from_corpus(corpus)
    if not prefix:
        return issues, review_paths
    review_re = re.compile(rf"{re.escape(prefix)}-e\d+(\d+)\.md$")

    for path in sorted(eval_dir.glob(f"{prefix}-e*.md")):
        match = review_re.search(path.name)
        if not match:
            continue
        seq = int(match.group(1))
        dimension = ""
        for item in corpus["dimensions"]:
            if item["review"]["seq"] == seq:
                dimension = str(item.get("legacy_alias") or item["id"])
                break
        if not dimension:
            continue
        review_paths.append(path.as_posix())
        for row in parse_review_file(path):
            issues.append({**row, "dimension": dimension})
    return issues, review_paths


def build_dimensions(
    eval_state: dict[str, str],
    *,
    corpus: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    if corpus is None and eval_state.get("corpus_ref", ""):
        raise ValueError(
            "corpus is required for build_dimensions when evaluate-state has corpus_ref",
        )
    dim_map = dimension_status_legacy_map(eval_state, corpus=corpus)
    counts = parse_issue_counts(eval_state.get("issue_counts", "{}"))
    if corpus is None:
        dimensions = []
        for dim, status in dim_map.items():
            if status == "pending":
                continue
            entry = counts.get(dim, {"total": "0", "resolved": "0"})
            dimensions.append({
                "dim": dim,
                "status": status,
                "total": entry.get("total", "0"),
                "resolved": entry.get("resolved", "0"),
            })
        return dimensions

    dimensions: list[dict[str, str]] = []
    for item in corpus["dimensions"]:
        alias = str(item.get("legacy_alias") or item["id"])
        dim_id = str(item["id"])
        status = dim_map.get(alias, "pending")
        if status == "pending":
            continue
        entry = counts.get(dim_id, {"total": "0", "resolved": "0"})
        dimensions.append({
            "dim": alias,
            "status": status,
            "total": entry.get("total", "0"),
            "resolved": entry.get("resolved", "0"),
        })
    return dimensions


def count_ignored(issues: list[dict[str, str]]) -> int:
    return sum(
        1 for issue in issues if issue.get("decision", "").lower() == "ignore"
    )


def _reason_from_issue(issue: dict[str, str]) -> str:
    issue_id = issue.get("id", "")
    description = issue.get("description", "")
    if issue_id and description:
        reason = f"{issue_id}: {description}"
    else:
        reason = description or issue_id
    if issue.get("status", "").lower() == "accepted-divergence":
        return f"accepted-divergence: {reason}"
    return reason


def compute_fix_severity(
    issues: list[dict[str, str]],
) -> tuple[str, str]:
    """Return fix_severity and fix_severity_reason from parsed review issues."""
    if not issues:
        return "minor", ""

    ranked = sorted(
        issues,
        key=lambda issue: _SEVERITY_RANK.get(
            issue.get("severity", "").lower(),
            0,
        ),
        reverse=True,
    )
    top = ranked[0]
    severity = top.get("severity", "minor").lower()
    if severity not in _SEVERITY_RANK:
        severity = "minor"
    if all(issue.get("decision", "").lower() == "ignore" for issue in issues):
        severity = "minor"
    return severity, _reason_from_issue(top)


def build_issue_counts(
    eval_state: dict[str, str],
    issues: list[dict[str, str]],
) -> dict[str, int]:
    total_issues = int(eval_state.get("total_issues", "0") or "0")
    resolved_issues = int(eval_state.get("resolved_issues", "0") or "0")
    ignored_issues = count_ignored(issues)
    if ignored_issues == 0 and total_issues > resolved_issues:
        ignored_issues = total_issues - resolved_issues
    return {
        "total_issues": total_issues,
        "resolved_issues": resolved_issues,
        "ignored_issues": ignored_issues,
    }


def _focus_phase(cycle_id: str, project_root: Path) -> str:
    return _adapter().session_context(cycle_id, project_root).focus_phase


def _load_evaluating_context(
    cycle_id: str,
    project_root: Path,
) -> tuple[dict[str, str], Path, dict[str, str], int, int, str] | dict[str, Any]:
    """Return (state, ws_path, eval_data, evaluate_round, active_doc, mode) or failure."""
    ws_path = _adapter().resolve_workflow_state_path(cycle_id, project_root)
    state = _adapter().load_workflow_state(cycle_id, project_root)
    current = state["current_state"]
    if current != _EXPECTED_SESSION_STATE:
        return _failure(
            "",
            (
                f"current state is {current!r}, "
                f"expected {_EXPECTED_SESSION_STATE!r}."
            ),
            current_state=current,
        )
    phase = _focus_phase(cycle_id, project_root)
    if phase != _EXPECTED_FOCUS_PHASE:
        return _failure(
            "",
            (
                f"focus phase is {phase!r}, "
                f"expected {_EXPECTED_FOCUS_PHASE!r}."
            ),
            current_state=current,
        )

    es_path = _evaluate_state_path(cycle_id, project_root)
    if not es_path.exists():
        return _failure(
            "",
            "evaluate-state.md not found.",
            current_state=current,
        )

    raw_state = parse_frontmatter_fields(es_path.read_text(encoding="utf-8"))
    if not is_v8_state(raw_state):
        return _failure(
            "",
            "incompatible_round: evaluate-state must be v8",
            current_state=current,
        )
    try:
        eval_data = load_evaluate_state(es_path)
    except ValueError as exc:
        return _failure("", str(exc), current_state=current)

    evaluate_round = 0
    context = _handoff_context()
    if context:
        try:
            evaluate_round = int(context.get("evaluate_round", 0))
        except (TypeError, ValueError):
            evaluate_round = 0
    if evaluate_round < 1:
        try:
            evaluate_round = int(eval_data.get("evaluate_round", "0"))
        except ValueError:
            evaluate_round = 0
    if evaluate_round < 1:
        try:
            evaluate_round = int(state.get("evaluate_round", "0"))
        except ValueError:
            evaluate_round = 0
    if evaluate_round < 1:
        return _failure(
            "",
            f"evaluate_round is {evaluate_round!r} (expected >= 1).",
            current_state=current,
        )

    active_doc = _adapter().session_context(cycle_id, project_root).active_doc
    mode = state["mode"]
    return state, ws_path, eval_data, evaluate_round, active_doc, mode


def build_eval_loop_payload(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Build eval loop context (requires Working + focus evaluating + evaluate-state)."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_BEGIN_EVAL_ROUND
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    es_path = _evaluate_state_path(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    return _success(
        _CMD_BEGIN_EVAL_ROUND,
        current_state=state["current_state"],
        mode=mode,
        dispatch=dispatch_list(cycle_id, project_root),
        corpus_ref=eval_data.get("corpus_ref", ""),
        dimension_dispatch=eval_data.get("dimension_dispatch", "parallel"),
        evaluate_round=evaluate_round,
        M=evaluate_round,
        active_doc=active_doc,
        N=active_doc,
        cycle_type=_adapter().detect_cycle_type(cycle_id),
        upstream_baseline_ref=_upstream_baseline_ref(cycle_id, project_root),
        project_root=project_root.resolve().as_posix(),
        paths=paths,
    )


def _start_next_eval_round(
    cycle_id: str,
    project_root: Path,
    *,
    state: dict[str, str],
    ws_path: Path,
    mode: str,
) -> dict[str, Any]:
    """Admit the next evaluate round and return the loop payload."""
    del ws_path, state, mode
    admitted = _admit_eval_round(cycle_id, project_root)
    if admitted is not None:
        return admitted
    return build_eval_loop_payload(cycle_id, project_root)


def _v5_incompatible_reason(es_path: Path) -> str | None:
    """Return a hard-cut incompatibility for any existing non-v8 state."""
    if not es_path.is_file():
        return None
    raw_state = parse_frontmatter_fields(es_path.read_text(encoding="utf-8"))
    if is_v8_state(raw_state):
        return None
    return (
        "incompatible_round: evaluate-state version "
        f"{raw_state.get('version')!r} is not supported (expected '8')"
    )


def _require_admission_protocol() -> str | None:
    adapter = _adapter()
    missing = [
        name
        for name in (
            "eval_admission_context",
            "prepare_eval_admission",
            "abort_eval_admission",
        )
        if not callable(getattr(adapter, name, None))
    ]
    if missing:
        return "adapter missing admission protocol: " + ", ".join(missing)
    return None


def _admit_eval_round(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any] | None:
    """Run two-phase admission. Return a failure payload, or None on success."""
    protocol_error = _require_admission_protocol()
    if protocol_error:
        return _failure(_CMD_BEGIN_EVAL_ROUND, protocol_error)
    adapter = _adapter()
    try:
        ctx = adapter.eval_admission_context(cycle_id, project_root)
    except (OSError, ValueError) as exc:
        return _failure(_CMD_BEGIN_EVAL_ROUND, str(exc))
    es_path = adapter.resolve_evaluate_state_path(cycle_id, project_root)
    evaluate_dir = Path(
        adapter.eval_paths(
            cycle_id,
            project_root,
            active_doc=adapter.session_context(cycle_id, project_root).active_doc,
            evaluate_round=ctx.candidate_round,
            es_path=es_path,
        )["evaluate_dir"]
    )
    try:
        recovery = recover_admission(
            ctx,
            evaluate_state_path=es_path,
            evaluate_dir=evaluate_dir,
            focus_phase=_focus_phase(cycle_id, project_root),
        )
    except ValueError as exc:
        return _failure(_CMD_BEGIN_EVAL_ROUND, str(exc))
    if recovery["action"] == "committed":
        try:
            _refresh_handoff(cycle_id, project_root, require_evaluating=True)
        except ValueError as exc:
            return _failure(_CMD_BEGIN_EVAL_ROUND, str(exc))
        return None

    token = ""
    try:
        journal = load_journal(ctx.admission_root)
        if (
            journal
            and str(journal.get("status")) in {"prepared", "transitioned"}
            and str(journal.get("snapshot_digest") or "")
        ):
            token = str(journal["token"])
            digest = str(journal["snapshot_digest"])
            prepared = {
                "ok": True,
                "token": token,
                "snapshot_digest": digest,
                "snapshot_ref": SNAPSHOT_REF,
                "skip_reasons": dict(journal.get("skip_reasons") or {}),
                "corpus": load_prepared_admission_corpus(
                    ctx.admission_root,
                    token=token,
                    evaluate_dir=evaluate_dir,
                    expected_digest=digest,
                ),
            }
        else:
            prepared = adapter.prepare_eval_admission(cycle_id, project_root)
            if not prepared.get("ok"):
                return _failure(
                    _CMD_BEGIN_EVAL_ROUND,
                    str(prepared.get("error") or "prepare_eval_admission failed"),
                )
            token = str(prepared["token"])

        entered = False
        if _focus_phase(cycle_id, project_root) != _EXPECTED_FOCUS_PHASE:
            entry = adapter.enter_evaluating(
                cycle_id,
                project_root,
                admission_token=token,
            )
            if not entry.get("ok"):
                adapter.abort_eval_admission(cycle_id, project_root, token=token)
                return _failure(
                    _CMD_BEGIN_EVAL_ROUND,
                    str(
                        entry.get("error")
                        or (entry.get("resume") or {}).get("action")
                        or "cannot enter evaluating"
                    ),
                    current_state=entry.get("current_state", ""),
                )
            entered = True
        post_ctx = adapter.eval_admission_context(cycle_id, project_root)
        if post_ctx.target_digest != ctx.target_digest:
            raise ValueError("admission target digest drifted after prepare")
        if not entered:
            mark_transitioned(
                ctx.admission_root,
                token=token,
                provider_state_fingerprint=post_ctx.provider_state_fingerprint,
            )

        handoff = _refresh_handoff(cycle_id, project_root, require_evaluating=True)
        from eval_adapter_config import validate_adapter_protocol  # noqa: WPS433

        adapter_capability = ""
        for name in ("EVAL_CAPABILITY", "_EVAL_CAPABILITY"):
            adapter_capability = str(getattr(adapter, name, "") or "").strip()
            if adapter_capability in {"full-remediation", "probe-only"}:
                break
        validate_adapter_protocol(
            adapter,
            eval_capability=adapter_capability or _eval_capability(),
            handoff=handoff,
        )
        context = handoff["context"]
        journal = load_journal(ctx.admission_root)
        if journal is None:
            raise ValueError("admission journal missing after transition")
        if str(context.get("session_key")) != str(journal.get("session_key")):
            raise ValueError("handoff session_key does not match admission journal")
        if int(context.get("evaluate_round") or 0) != int(
            journal.get("candidate_round") or 0
        ):
            raise ValueError("handoff evaluate_round does not match admission journal")
        post_handoff = adapter.eval_admission_context(cycle_id, project_root)
        if post_handoff.target_digest != str(journal.get("target_digest") or ""):
            raise ValueError("handoff target digest does not match admission journal")
        if post_handoff.provider_state_fingerprint != str(
            journal.get("provider_state_fingerprint") or ""
        ):
            raise ValueError(
                "handoff provider fingerprint does not match admission journal"
            )
        lease_id = str(context.get("lease_id") or "")
        if lease_id:
            record_handoff_lease(
                ctx.admission_root,
                token=token,
                lease_id=lease_id,
            )

        published = snapshot_dir(Path(str(context["evaluate_dir"])))
        digest = str(prepared["snapshot_digest"])
        if not published.is_dir():
            publish_prepared_snapshot(
                ctx.admission_root,
                token=token,
                evaluate_dir=Path(str(context["evaluate_dir"])),
                expected_digest=digest,
            )
        else:
            load_materialized_corpus(published, expected_digest=digest)

        skip_reasons = dict(prepared.get("skip_reasons") or {})
        if not this_attempt_is_committed(
            es_path,
            evaluate_round=int(ctx.candidate_round),
        ):
            existing_done = False
            if es_path.is_file():
                existing_done = (
                    str(
                        parse_frontmatter_fields(
                            es_path.read_text(encoding="utf-8")
                        ).get("eval_status")
                        or ""
                    )
                    == "done"
                )
            initial = build_initial_evaluate_state_for_corpus(
                prepared["corpus"],
                eval_capability=_eval_capability(),
                cycle_type=adapter.detect_cycle_type(cycle_id),
                evaluate_round=int(context["evaluate_round"]),
                focus_l=str(context.get("session_key") or ""),
                corpus_digest=digest,
                corpus_snapshot_ref=str(prepared.get("snapshot_ref") or SNAPSHOT_REF),
                skipped_ids=list(skip_reasons),
                skip_reasons=skip_reasons,
            )
            error = _commit_staged_evaluate_state(
                cycle_id,
                project_root,
                state=initial,
                set_phase_evaluating=True,
                previous_done_required=existing_done,
            )
            if error is not None:
                adapter.abort_eval_admission(cycle_id, project_root, token=token)
                return _failure(_CMD_BEGIN_EVAL_ROUND, error)
        finalize_admission(ctx.admission_root, token)
        return None
    except Exception as exc:
        if token:
            try:
                adapter.abort_eval_admission(cycle_id, project_root, token=token)
            except Exception:
                pass
        return _failure(_CMD_BEGIN_EVAL_ROUND, str(exc))


def begin_eval_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Enter focus evaluating or start next eval round; return payload."""
    ws_path = _adapter().resolve_workflow_state_path(cycle_id, project_root)
    state = _adapter().load_workflow_state(cycle_id, project_root)
    current = state["current_state"]
    mode = state["mode"]
    es_path = _evaluate_state_path(cycle_id, project_root)

    if current != _EXPECTED_SESSION_STATE:
        return _failure(
            _CMD_BEGIN_EVAL_ROUND,
            (
                f"cannot enter evaluating from state {current!r} "
                f"(expected {_EXPECTED_SESSION_STATE!r})."
            ),
            current_state=current,
        )

    if _focus_phase(cycle_id, project_root) == _EXPECTED_FOCUS_PHASE:
        if not es_path.exists():
            admitted = _admit_eval_round(cycle_id, project_root)
            if admitted is not None:
                return admitted
            es_path = _evaluate_state_path(cycle_id, project_root)
            if not es_path.exists():
                return _failure(
                    _CMD_BEGIN_EVAL_ROUND,
                    "incompatible_round: evaluating without EvalState or admission journal",
                    current_state=current,
                )

        raw_state = parse_frontmatter_fields(es_path.read_text(encoding="utf-8"))
        if not is_v8_state(raw_state):
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                "incompatible_round: evaluate-state must be v8",
                current_state=current,
            )
        try:
            eval_data = load_evaluate_state(es_path)
        except ValueError as exc:
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                str(exc),
                current_state=current,
            )

        eval_status = eval_data.get("eval_status", "")
        if eval_status == "done":
            return _start_next_eval_round(
                cycle_id,
                project_root,
                state=state,
                ws_path=ws_path,
                mode=mode,
            )
        if eval_status == "abandoned":
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                "evaluation was abandoned (eval_status: abandoned).",
                current_state=current,
            )

        mismatch = _validate_evaluate_state_for_session(
            eval_data, cycle_id, project_root
        )
        if mismatch:
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                mismatch,
                current_state=current,
            )
        try:
            adapter = _adapter()
            ctx = adapter.eval_admission_context(cycle_id, project_root)
            recover_admission(
                ctx,
                evaluate_state_path=es_path,
                evaluate_dir=Path(
                    adapter.eval_paths(
                        cycle_id,
                        project_root,
                        active_doc=adapter.session_context(
                            cycle_id, project_root
                        ).active_doc,
                        evaluate_round=ctx.candidate_round,
                        es_path=es_path,
                    )["evaluate_dir"]
                ),
                focus_phase=_EXPECTED_FOCUS_PHASE,
            )
        except (OSError, ValueError) as exc:
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                str(exc),
                current_state=current,
            )
        return build_eval_loop_payload(cycle_id, project_root)

    incompatible = _v5_incompatible_reason(es_path)
    if incompatible:
        return _failure(
            _CMD_BEGIN_EVAL_ROUND,
            incompatible,
            current_state=current,
        )

    admitted = _admit_eval_round(cycle_id, project_root)
    if admitted is not None:
        return admitted

    state = _adapter().load_workflow_state(cycle_id, project_root)
    es_path = _evaluate_state_path(cycle_id, project_root)
    try:
        eval_data = load_evaluate_state(es_path)
    except ValueError as exc:
        return _failure(
            _CMD_BEGIN_EVAL_ROUND,
            str(exc),
            current_state=state["current_state"],
        )

    mismatch = _validate_evaluate_state_for_session(
        eval_data, cycle_id, project_root
    )
    if mismatch:
        return _failure(
            _CMD_BEGIN_EVAL_ROUND,
            mismatch,
            current_state=state["current_state"],
        )

    return build_eval_loop_payload(cycle_id, project_root)


def _operations_path(paths: dict[str, str]) -> Path:
    """Return the Script-owned runtime record path for this Eval round."""
    return Path(paths["evaluate_dir"]) / "eval-operations.json"


def _format_ctx_dispatch_input(operation_ctx: dict[str, Any]) -> str:
    """Format the token-scoped runner context without session paths."""
    fields = (
        "round_token",
        "dimension_token",
        "dimension_id",
        "operation_kind",
        "target_digest",
        "staging_scope",
        "allowed_submission",
    )
    lines = [f"{field.upper()}: {operation_ctx[field]}" for field in fields]
    lines.append(
        "RESOLVED_METHOD: "
        + json.dumps(operation_ctx["resolved_method"], ensure_ascii=False),
    )
    lines.append(
        "RESOLVED_SOTS: "
        + json.dumps(operation_ctx["resolved_sots"], ensure_ascii=False),
    )
    return "\n".join(lines)


def _dimension_def(expanded_corpus: dict[str, Any], dim: str) -> dict[str, Any]:
    canonical = resolve_dim_id(expanded_corpus, dim)
    for item in expanded_corpus["dimensions"]:
        if item["id"] == canonical:
            return item
    raise ValueError(f"unknown dimension: {dim!r}")


def init_round(
    cycle_id: str,
    project_root: Path,
    *,
    mode: str | None = None,
) -> dict[str, Any]:
    """Retired: admission now goes through begin-eval-round only."""
    del cycle_id, project_root, mode
    return _failure(
        _CMD_INIT_ROUND,
        "init-round is retired; use begin-eval-round",
    )


def begin_dimension(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Mark a dimension in progress and return dimension-probe-runner input."""
    if not dim.strip():
        return _failure(
            _CMD_BEGIN_DIMENSION,
            "invalid dim: empty string",
        )

    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_BEGIN_DIMENSION
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if not _dispatch_dim_allowed(cycle_id, project_root, dim):
        return _failure(
            _CMD_BEGIN_DIMENSION,
            f"invalid dim: {dim!r} (not in corpus for mode {mode!r}).",
        )

    if eval_data.get("eval_phase") != "probe":
        return _failure(
            _CMD_BEGIN_DIMENSION,
            f"eval_phase is {eval_data.get('eval_phase')!r}, expected 'probe'.",
            current_state=state["current_state"],
        )

    es_path = _evaluate_state_path(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )

    corpus = _load_corpus(cycle_id, project_root)
    canonical_dim = _canonical_dim(cycle_id, project_root, dim)
    dimension_status = parse_dimension_status(eval_data["dimension_status"])
    if dimension_status.get(canonical_dim) == "skipped":
        reasons = parse_skip_reason(eval_data.get("skip_reason", "{}"))
        return _success(
            _CMD_BEGIN_DIMENSION,
            dim=dim,
            skip=True,
            skip_reason=reasons.get(canonical_dim, ""),
            current_state=state["current_state"],
        )
    if dimension_status.get(canonical_dim) != "pending":
        return _failure(
            _CMD_BEGIN_DIMENSION,
            f"dimension is not pending: {canonical_dim!r}",
            dim=dim,
        )

    expanded = _expanded_corpus(
        cycle_id,
        state,
        paths,
        evaluate_round,
        project_root=project_root,
    )
    dim_def = _dimension_def(expanded, dim)
    try:
        operation_ctx = issue_probe_context(
            operations_path=_operations_path(paths),
            write_staging_dir=Path(
                paths.get("write_staging_dir") or paths["evaluate_dir"],
            ),
            target_path=Path(str(dim_def["eval_target"]["path"])),
            round_token=eval_data["round_token"],
            dimension_id=canonical_dim,
            method=dict(dim_def["method"]),
            sots=[dict(sot) for sot in dim_def["sots"]],
        )
    except (OSError, ValueError) as exc:
        return _failure(_CMD_BEGIN_DIMENSION, str(exc), dim=dim)

    def _patch(data: dict[str, str]) -> dict[str, str]:
        updated = merge_current_dimension(data, dim, "probing", corpus=corpus)
        if paths.get("session_key"):
            updated["focus_l"] = str(paths["session_key"])
        updated["evaluate_round"] = str(evaluate_round)
        return updated

    error = _commit_staged_evaluate_state(
        cycle_id,
        project_root,
        update=_patch,
    )
    if error is not None:
        try:
            discard_operation_context(
                operations_path=_operations_path(paths),
                dimension_token=operation_ctx["dimension_token"],
            )
        except (OSError, ValueError):
            pass
        return _failure(_CMD_BEGIN_DIMENSION, error, dim=dim)

    return _success(
        _CMD_BEGIN_DIMENSION,
        dim=dim,
        current_state=state["current_state"],
        operation_ctx=operation_ctx,
        dispatch_input=_format_ctx_dispatch_input(operation_ctx),
    )


def read_b_snapshot_cmd(
    cycle_id: str,
    project_root: Path,
    *,
    dimension_token: str,
) -> dict[str, Any]:
    """Return a token-authorized read-only snapshot of EvalTarget B."""
    if not dimension_token.strip():
        return _failure(_CMD_READ_B_SNAPSHOT, "invalid dimension_token: empty string")
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_READ_B_SNAPSHOT
        return ctx
    _state, _ws_path, eval_data, evaluate_round, active_doc, _mode = ctx
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=_evaluate_state_path(cycle_id, project_root),
    )
    try:
        snapshot = read_target_snapshot(
            operations_path=_operations_path(paths),
            dimension_token=dimension_token,
        )
    except ValueError as exc:
        return _failure(_CMD_READ_B_SNAPSHOT, str(exc))
    return _success(
        _CMD_READ_B_SNAPSHOT,
        dimension_token=dimension_token,
        round_token=eval_data["round_token"],
        target_digest=snapshot["digest"],
        content=snapshot["content"],
    )


def read_evidence_snapshot_cmd(
    cycle_id: str,
    project_root: Path,
    *,
    dimension_token: str,
    evidence_ref: str,
) -> dict[str, Any]:
    """Return token-authorized dynamic SoT evidence content."""
    if not dimension_token.strip():
        return _failure(
            _CMD_READ_EVIDENCE_SNAPSHOT,
            "invalid dimension_token: empty string",
        )
    if not evidence_ref.strip():
        return _failure(
            _CMD_READ_EVIDENCE_SNAPSHOT,
            "invalid evidence_ref: empty string",
        )
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_READ_EVIDENCE_SNAPSHOT
        return ctx
    _state, _ws_path, _eval_data, evaluate_round, active_doc, _mode = ctx
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=_evaluate_state_path(cycle_id, project_root),
    )
    try:
        snapshot = read_evidence_snapshot(
            operations_path=_operations_path(paths),
            dimension_token=dimension_token,
            evidence_ref=evidence_ref,
        )
    except ValueError as exc:
        return _failure(_CMD_READ_EVIDENCE_SNAPSHOT, str(exc))
    return _success(
        _CMD_READ_EVIDENCE_SNAPSHOT,
        dimension_token=dimension_token,
        evidence_ref=evidence_ref,
        digest=snapshot["digest"],
        content=snapshot["content"],
    )


def _load_probe_payload(path: Path) -> tuple[dict[str, Any], str]:
    """Load and normalize the minimal token-scoped probe submission payload."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read payload file: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid probe payload JSON: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != _PROBE_PAYLOAD_KEYS:
        raise ValueError(
            "probe payload must contain only dimension_token and findings",
        )
    token = payload.get("dimension_token")
    findings = payload.get("findings")
    if not isinstance(token, str) or not token.strip():
        raise ValueError("probe payload dimension_token must be a non-empty string")
    if not isinstance(findings, list):
        raise ValueError("probe payload findings must be an array")

    finding_ids: set[str] = set()
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ValueError(f"findings[{index}] must be an object")
        if "handling_mode" in finding:
            raise ValueError(
                f"findings[{index}] must not supply Control-owned handling_mode",
            )
        allowed = _FINDING_REQUIRED_KEYS | _FINDING_OPTIONAL_KEYS
        if not _FINDING_REQUIRED_KEYS <= set(finding) or set(finding) - allowed:
            raise ValueError(
                f"findings[{index}] must contain required review fields only",
            )
        for field, value in finding.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"findings[{index}].{field} must be a non-empty string")
            if any(character in value for character in ("\n", "\r", "|")):
                raise ValueError(
                    f"findings[{index}].{field} cannot contain table delimiters",
                )
        finding_id = finding["id"]
        if finding_id in finding_ids:
            raise ValueError(f"duplicate finding id: {finding_id}")
        finding_ids.add(finding_id)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return payload, hashlib.sha256(canonical.encode("utf-8")).hexdigest()




def prepare_remediation_at(
    *,
    operations_path: Path,
    proposal_file: Path,
) -> dict[str, Any]:
    """Validate and canonicalize a proposal without writing any Eval-owned file."""
    try:
        candidate = json.loads(proposal_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read proposal file: {proposal_file}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid remediation proposal JSON: {exc}") from exc
    if not isinstance(candidate, dict):
        raise ValueError("remediation proposal must be an object")
    operation_token = candidate.get("operation_token")
    if not isinstance(operation_token, str) or not operation_token:
        raise ValueError("remediation proposal operation_token must be non-empty")
    operation = get_operation_record(operations_path, operation_token)
    if operation.get("operation_kind") != "remediation":
        raise ValueError("operation_token is not a remediation operation")
    return prepare_remediation_proposal(operation, candidate)












def _render_probe_review(
    *,
    dimension_label: str,
    dimension_id: str,
    round_token: str,
    active_doc: int,
    evaluate_round: int,
    method_focus: str,
    handling_policy: str,
    findings: list[dict[str, Any]],
) -> str:
    """Render a validated ReviewFile without exposing its path to the runner."""
    content = render_review_header(
        dim_label=dimension_label,
        rev=active_doc,
        round_num=evaluate_round,
        date=date.today().isoformat(),
        refs=method_focus,
        dimension_id=dimension_id,
        round_token=round_token,
    )
    for finding in findings:
        row = {
            **finding,
            "handling_mode": handling_mode_for_issue(
                str(finding["root_cause"]),
                handling_policy,
            ),
            "sot_ref": finding.get("sot_ref", "—"),
            "status": "pending",
            "decision": "—",
            "resolution": "",
        }
        content += (
            f"| {row['id']} | {row['root_cause']} | {row['handling_mode']} | "
            f"{row['sot_ref']} | "
            f"{row['location']} | {row['severity']} | {row['evidence']} | "
            f"{row['description']} | {row['status']} | {row['decision']} | "
            f"{row['resolution']} |\n"
        )
    errors = validate_review_content(content, phase="probe")
    if errors:
        raise ValueError(f"generated review invalid: {'; '.join(errors)}")
    return content


def _atomic_write_text(path: Path, content: str) -> None:
    """Atomically replace one Eval-owned text file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.replace(temporary, path)


def _atomic_write_review(path: Path, content: str) -> None:
    """Write a ReviewFile under its dedicated lock."""
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            _atomic_write_text(path, content)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
















def _publish_probe_review(
    cycle_id: str,
    project_root: Path,
    *,
    paths: dict[str, str],
    evaluate_round: int,
    formal_review_path: Path,
    content: str,
) -> str | None:
    """Publish a control-generated review to its formal Eval location."""
    if formal_review_path.exists():
        return f"formal review already exists: {formal_review_path.as_posix()}"
    lease_id = str(paths.get("lease_id", "")).strip()
    if not lease_id:
        _atomic_write_text(formal_review_path, content)
        return None

    staging = Path(str(paths["write_staging_dir"]))
    staged = staging / formal_review_path.name
    _atomic_write_text(staged, content)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest = build_artifact_manifest_v2(
        lease_id=lease_id,
        session_key=str(paths.get("session_key", "")),
        evaluate_round=evaluate_round,
        staged_relative_path=formal_review_path.name,
        final_relative_path=formal_review_path.name,
        artifact_digest=digest,
    )
    result = _adapter().commit_eval_artifacts(
        cycle_id,
        project_root,
        manifest=manifest,
    )
    if not result.get("ok"):
        staged.unlink(missing_ok=True)
        return str(result.get("error") or "commit-artifacts failed")
    return None


def submit_probe_findings(
    cycle_id: str,
    project_root: Path,
    *,
    payload_file: Path,
) -> dict[str, Any]:
    """Validate, publish, and record one token-scoped probe submission."""
    try:
        payload, _caller_digest = _load_probe_payload(payload_file)
    except ValueError as exc:
        return _failure(_CMD_SUBMIT_PROBE_FINDINGS, str(exc))

    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_SUBMIT_PROBE_FINDINGS
        return ctx
    state, _ws_path, eval_data, evaluate_round, active_doc, _mode = ctx
    dimension_token = str(payload["dimension_token"])
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=_evaluate_state_path(cycle_id, project_root),
    )
    operations_path = _operations_path(paths)
    try:
        record = get_operation_record(operations_path, dimension_token)
    except ValueError as exc:
        return _failure(_CMD_SUBMIT_PROBE_FINDINGS, str(exc))
    if (
        record.get("operation_kind") != "probe"
        or record.get("round_token") != eval_data["round_token"]
    ):
        return _failure(
            _CMD_SUBMIT_PROBE_FINDINGS,
            "operation_token is not authorized for this probe round",
            dimension_token=dimension_token,
        )

    dimension_id = str(record["dimension_id"])
    policies = parse_handling_policy(eval_data["handling_policy"])
    handling_policy = policies.get(dimension_id)
    if handling_policy is None:
        return _failure(
            _CMD_SUBMIT_PROBE_FINDINGS,
            f"handling_policy missing dimension: {dimension_id!r}",
        )
    canonical_findings = [
        {
            **finding,
            "handling_mode": handling_mode_for_issue(
                str(finding["root_cause"]),
                handling_policy,
            ),
        }
        for finding in payload["findings"]
    ]
    submission_digest = hashlib.sha256(
        json.dumps(
            canonical_findings,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8"),
    ).hexdigest()
    if record.get("phase") == "committed":
        if record.get("submission_digest") == submission_digest:
            return _success(
                _CMD_SUBMIT_PROBE_FINDINGS,
                dimension_token=dimension_token,
                outcome="probed",
                idempotent=True,
                review_path=record.get("review_path", ""),
            )
        return _failure(
            _CMD_SUBMIT_PROBE_FINDINGS,
            "conflict: different submission for operation_token",
            dimension_token=dimension_token,
        )
    if record.get("phase") in {"prepared", "target-applied", "review-applied"}:
        if record.get("submission_digest") != submission_digest:
            return _failure(
                _CMD_SUBMIT_PROBE_FINDINGS,
                "conflict: different submission for operation_token",
                dimension_token=dimension_token,
            )
        recovered = _forward_recover_to_committed(
            cycle_id,
            project_root,
            command=_CMD_SUBMIT_PROBE_FINDINGS,
            operations_path=operations_path,
            record=record,
            paths=paths,
            review_path=Path(str(record.get("review_path") or "")),
            evaluate_round=evaluate_round,
        )
        if not recovered.get("ok"):
            return recovered
        record = recovered["record"]
        review_path = Path(str(record.get("review_path") or ""))
        corpus = _load_corpus(cycle_id, project_root)
        total_issues = len(record.get("canonical_findings") or [])

        def _recover_patch(data: dict[str, str]) -> dict[str, str]:
            next_status = "complete" if total_issues == 0 else "probed"
            updated = merge_current_dimension(
                data,
                dimension_id,
                next_status,
                corpus=corpus or None,
            )
            return _recompute_aggregate_counts(
                patch_issue_count(updated, dimension_id, total=str(total_issues)),
            )

        error = _commit_staged_evaluate_state(
            cycle_id,
            project_root,
            update=_recover_patch,
        )
        if error is not None:
            return _failure(
                _CMD_SUBMIT_PROBE_FINDINGS,
                f"projection_pending: {error}",
            )
        return _success(
            _CMD_SUBMIT_PROBE_FINDINGS,
            dimension_token=dimension_token,
            operation_token=dimension_token,
            outcome="probed",
            idempotent=False,
            total_issues=str(total_issues),
            review_path=review_path.resolve().as_posix() if review_path else "",
            findings=record.get("canonical_findings") or [],
        )
    if record.get("phase") != "context-open":
        return _failure(
            _CMD_SUBMIT_PROBE_FINDINGS,
            f"repair_required: probe operation phase is {record.get('phase')!r}",
        )
    if parse_dimension_status(eval_data["dimension_status"]).get(
        dimension_id,
    ) != "probing":
        return _failure(
            _CMD_SUBMIT_PROBE_FINDINGS,
            "operation_token does not own a probing dimension",
        )

    expanded = _expanded_corpus(
        cycle_id,
        state,
        paths,
        evaluate_round,
        project_root=project_root,
    )
    dim_def = _dimension_def(expanded, dimension_id)
    try:
        review_content = _render_probe_review(
            dimension_label=str(dim_def["label"]),
            dimension_id=dimension_id,
            round_token=str(eval_data["round_token"]),
            active_doc=active_doc,
            evaluate_round=evaluate_round,
            method_focus=str(dim_def["method"].get("focus", "")),
            handling_policy=handling_policy,
            findings=payload["findings"],
        )
    except (OSError, ValueError) as exc:
        return _failure(_CMD_SUBMIT_PROBE_FINDINGS, str(exc))
    review_path = _review_path_for_dim(
        Path(paths["evaluate_dir"]),
        cycle_id=cycle_id,
        state=state,
        paths=paths,
        evaluate_round=evaluate_round,
        dim=dimension_id,
        project_root=project_root,
    )
    review_digest = hashlib.sha256(review_content.encode("utf-8")).hexdigest()
    prepared = {
        **record,
        "phase": "prepared",
        "submission_digest": submission_digest,
        "target_effect": "none",
        "target_after_digest": record["target_base_digest"],
        "review_after_digest": review_digest,
        "canonical_findings": canonical_findings,
        "remediation_application": None,
        "review_before_content": None,
        "review_after_content": review_content,
        "target_staged_path": None,
        "review_path": review_path.resolve().as_posix(),
    }
    try:
        record = _advance_phase(operations_path, prepared, "prepared")
    except ValueError as exc:
        return _failure(_CMD_SUBMIT_PROBE_FINDINGS, str(exc))
    recovered = _forward_recover_to_committed(
        cycle_id,
        project_root,
        command=_CMD_SUBMIT_PROBE_FINDINGS,
        operations_path=operations_path,
        record=record,
        paths=paths,
        review_path=review_path,
        evaluate_round=evaluate_round,
    )
    if not recovered.get("ok"):
        return recovered
    record = recovered["record"]

    corpus = _load_corpus(cycle_id, project_root)
    total_issues = len(canonical_findings)

    def _patch(data: dict[str, str]) -> dict[str, str]:
        next_status = "complete" if total_issues == 0 else "probed"
        updated = merge_current_dimension(
            data,
            dimension_id,
            next_status,
            corpus=corpus,
        )
        return _recompute_aggregate_counts(
            patch_issue_count(updated, dimension_id, total=str(total_issues)),
        )

    error = _commit_staged_evaluate_state(cycle_id, project_root, update=_patch)
    if error is not None:
        return _failure(
            _CMD_SUBMIT_PROBE_FINDINGS,
            f"projection_pending: {error}",
        )
    return _success(
        _CMD_SUBMIT_PROBE_FINDINGS,
        dimension_token=dimension_token,
        operation_token=dimension_token,
        outcome="probed",
        idempotent=False,
        total_issues=str(total_issues),
        review_path=review_path.resolve().as_posix(),
        findings=canonical_findings,
    )






def check_dimension(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Read-only verify a dimension after dimension-probe-runner."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_CHECK_DIMENSION
        ctx["dim"] = dim
        ctx["outcome"] = "incomplete"
        ctx["abandoned"] = False
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if not _dispatch_dim_allowed(cycle_id, project_root, dim):
        return _failure(
            _CMD_CHECK_DIMENSION,
            f"invalid dim: {dim!r} (not in corpus for mode {mode!r}).",
            current_state=state["current_state"],
            dim=dim,
            outcome="incomplete",
            abandoned=False,
        )

    eval_status = eval_data.get("eval_status", "")
    if eval_status == "abandoned":
        return _success(
            _CMD_CHECK_DIMENSION,
            dim=dim,
            outcome="abandoned",
            abandoned=True,
            current_state=state["current_state"],
            eval_status=eval_status,
        )

    corpus = _load_corpus(cycle_id, project_root)
    dim_map = dimension_status_legacy_map(eval_data, corpus=corpus)
    dim_status = dim_map.get(dim, "pending")
    dim_id = _canonical_dim(cycle_id, project_root, dim)

    review_path = _review_path_from_context(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
        dim=dim,
    )

    if review_path.exists() and dim_status not in {"probed", "complete"}:
        return _failure(
            _CMD_CHECK_DIMENSION,
            (
                f"review exists but {dim} status is {dim_status!r}, "
                "expected 'probed' or 'complete'."
            ),
            current_state=state["current_state"],
            dim=dim,
            outcome="incomplete",
            abandoned=False,
            dim_status=dim_status,
            review_path=review_path.resolve().as_posix(),
        )

    if dim_status not in {"probed", "complete"}:
        return _failure(
            _CMD_CHECK_DIMENSION,
            f"{dim} status is {dim_status!r}, expected 'probed' or 'complete'.",
            current_state=state["current_state"],
            dim=dim,
            outcome="incomplete",
            abandoned=False,
            dim_status=dim_status,
        )

    validation_errors = validate_review_file(review_path, phase="probe")
    if validation_errors:
        return _failure(
            _CMD_CHECK_DIMENSION,
            "; ".join(validation_errors),
            current_state=state["current_state"],
            dim=dim,
            outcome="incomplete",
            abandoned=False,
            review_path=review_path.resolve().as_posix(),
        )

    rows = parse_review_file(review_path)
    for row in rows:
        row["dimension"] = dim

    counts = parse_issue_counts(eval_data.get("issue_counts", "{}"))
    dim_total = counts.get(dim_id, {}).get("total", "0")

    return _success(
        _CMD_CHECK_DIMENSION,
        dim=dim,
        outcome="probed",
        abandoned=False,
        current_state=state["current_state"],
        eval_status=eval_status,
        dim_status=dim_status,
        total_issues=dim_total,
        review_path=review_path.resolve().as_posix(),
        issues=rows,
    )


def _probe_result_issues(
    *,
    cycle_id: str,
    project_root: Path,
    eval_data: dict[str, str],
    paths: dict[str, str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return submitted findings, preserving caller-owned routing metadata."""
    fallback_issues, review_paths = collect_review_issues(
        Path(paths["evaluate_dir"]),
        cycle_id=cycle_id,
        project_root=project_root,
    )
    issues_by_dim: dict[str, list[dict[str, Any]]] = {}
    for issue in fallback_issues:
        dimension = str(issue.get("dimension", ""))
        try:
            dimension = _canonical_dim(cycle_id, project_root, dimension)
        except ValueError:
            continue
        issues_by_dim.setdefault(dimension, []).append(issue)

    records = load_operation_records(_operations_path(paths))["operations"]
    for record in records.values():
        dimension_id = str(record.get("dimension_id", ""))
        if (
            record.get("operation_kind") != "probe"
            or record.get("round_token") != eval_data.get("round_token")
            or record.get("phase") != "committed"
        ):
            continue
        findings = record.get("canonical_findings")
        if not isinstance(findings, list):
            continue
        issues_by_dim[dimension_id] = [
            {**finding, "dimension": dimension_id}
            for finding in findings
            if isinstance(finding, dict)
        ]

    issues: list[dict[str, Any]] = []
    for dimension_id in _dispatch_canonical(cycle_id, project_root):
        issues.extend(issues_by_dim.get(dimension_id, []))
    return issues, review_paths


def _application_outcome(record: dict[str, Any]) -> str | None:
    application = record.get("remediation_application")
    if not isinstance(application, dict):
        return None
    final = application.get("final")
    if not isinstance(final, dict):
        return None
    outcome = final.get("outcome")
    return str(outcome) if outcome is not None else None


def _committed_abandon_record(
    operations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    for record in operations:
        if (
            record.get("operation_kind") == "remediation"
            and record.get("phase") == "committed"
            and _application_outcome(record) == "abandon"
        ):
            return record
    return None


def _project_abandoned_round(
    cycle_id: str,
    project_root: Path,
    *,
    command: str,
    eval_data: dict[str, str],
    record: dict[str, Any],
    review_path: Path | None,
    extra_failure: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Rebuild abandoned/done from Review + committed abandon. None on success."""
    extra = extra_failure or {}
    dimension_id = str(record["dimension_id"])
    rows: list[dict[str, str]] = []
    if review_path is not None and review_path.is_file():
        try:
            rows = parse_review_file(
                review_path,
                expected_dimension_id=dimension_id,
                expected_round_token=str(eval_data["round_token"]),
            )
        except ValueError as exc:
            return _failure(command, str(exc), **extra)

    def _project(data: dict[str, str]) -> dict[str, str]:
        updated = dict(data)
        updated["eval_status"] = "abandoned"
        updated["eval_phase"] = "done"
        if rows:
            updated = patch_issue_count(
                updated,
                dimension_id,
                total=str(len(rows)),
                resolved=str(count_resolved(rows)),
            )
            updated = _recompute_aggregate_counts(updated)
        return updated

    error = _commit_staged_evaluate_state(cycle_id, project_root, update=_project)
    if error is not None:
        return _failure(command, f"projection_pending: {error}", **extra)
    eval_data["eval_status"] = "abandoned"
    eval_data["eval_phase"] = "done"
    return None


def _sync_committed_abandon_projection(
    cycle_id: str,
    project_root: Path,
    *,
    command: str,
    state: dict[str, str],
    eval_data: dict[str, str],
    evaluate_round: int,
    active_doc: int,
    paths: dict[str, str],
    refuse_new_context: bool = False,
    extra_failure: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Rebuild abandon projection on entry. Optionally refuse a new context."""
    extra = extra_failure or {}
    abandon = _committed_abandon_record(
        _operations_for_round(paths, eval_data["round_token"]),
    )
    if abandon is None:
        return None
    try:
        review_path = _review_path_from_context(
            cycle_id,
            project_root,
            state=state,
            evaluate_round=evaluate_round,
            active_doc=active_doc,
            dim=str(abandon["dimension_id"]),
        )
    except (OSError, ValueError):
        review_path = None
    blocked = _project_abandoned_round(
        cycle_id,
        project_root,
        command=command,
        eval_data=eval_data,
        record=abandon,
        review_path=review_path,
        extra_failure=extra,
    )
    if blocked is not None:
        return blocked
    if refuse_new_context:
        failure = _abandoned_failure(command, state, eval_data)
        if failure is not None:
            failure.update(extra)
        return failure
    return None


def _remediation_command_context(
    command: str,
    cycle_id: str,
    project_root: Path,
) -> tuple[
    dict[str, str],
    dict[str, str],
    int,
    int,
    dict[str, str],
] | dict[str, Any]:
    """Load common full-remediation command state and paths."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = command
        return ctx
    state, _ws_path, eval_data, evaluate_round, active_doc, _mode = ctx
    if eval_data.get("eval_capability") != "full-remediation":
        return _failure(
            command,
            "probe-only round rejects remediation commands",
        )
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=_evaluate_state_path(cycle_id, project_root),
    )
    synced = _sync_committed_abandon_projection(
        cycle_id,
        project_root,
        command=command,
        state=state,
        eval_data=eval_data,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
        paths=paths,
        refuse_new_context=command == _CMD_BEGIN_DIMENSION_REMEDIATION,
    )
    if synced is not None:
        return synced
    return state, eval_data, evaluate_round, active_doc, paths


def _operations_for_round(
    paths: dict[str, str],
    round_token: str,
) -> list[dict[str, Any]]:
    records = load_operation_records(_operations_path(paths))["operations"]
    return [
        record
        for record in records.values()
        if record.get("round_token") == round_token
    ]


def begin_remediation(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Enter unified remediation after every Probe operation is committed."""
    loaded = _remediation_command_context(
        _CMD_BEGIN_REMEDIATION,
        cycle_id,
        project_root,
    )
    if isinstance(loaded, dict):
        return loaded
    state, eval_data, evaluate_round, active_doc, paths = loaded
    phase = eval_data.get("eval_phase")
    if phase not in {"probe", "remediation"}:
        return _failure(
            _CMD_BEGIN_REMEDIATION,
            f"eval_phase is {phase!r}, expected 'probe' or 'remediation'",
        )
    dimensions = parse_dimension_status(eval_data["dimension_status"])
    active_dimensions = {
        dim_id: status
        for dim_id, status in dimensions.items()
        if status != "skipped"
    }
    if phase == "probe" and any(
        status not in {"probed", "complete"}
        for status in active_dimensions.values()
    ):
        return _failure(
            _CMD_BEGIN_REMEDIATION,
            "not all dimensions are probed or complete",
        )
    operations = _operations_for_round(paths, eval_data["round_token"])
    if any(
        record.get("operation_kind") == "probe"
        and record.get("phase") != "committed"
        for record in operations
    ):
        return _failure(
            _CMD_BEGIN_REMEDIATION,
            "open probe operation prevents remediation",
        )
    committed_probe_dimensions = {
        str(record.get("dimension_id"))
        for record in operations
        if record.get("operation_kind") == "probe"
        and record.get("phase") == "committed"
    }
    if not set(active_dimensions) <= committed_probe_dimensions:
        return _failure(
            _CMD_BEGIN_REMEDIATION,
            "missing committed probe operation for one or more dimensions",
        )
    probe_by_dimension = {
        str(record.get("dimension_id")): record
        for record in operations
        if record.get("operation_kind") == "probe"
        and record.get("phase") == "committed"
    }
    for dimension_id in active_dimensions:
        review_path = _review_path_from_context(
            cycle_id,
            project_root,
            state=state,
            evaluate_round=evaluate_round,
            active_doc=active_doc,
            dim=dimension_id,
        )
        if not review_path.is_file():
            return _failure(
                _CMD_BEGIN_REMEDIATION,
                f"ReviewFile missing for dimension {dimension_id!r}",
            )
        try:
            rows = parse_review_file(
                review_path,
                expected_dimension_id=dimension_id,
                expected_round_token=eval_data["round_token"],
            )
            validate_review_against_probe_record(
                rows,
                probe_by_dimension[dimension_id],
            )
            if any(row.get("status") == "resolved" for row in rows):
                validate_review_completion(
                    rows=rows,
                    dimension_id=dimension_id,
                    remediation_records=operations,
                    review_digest=hashlib.sha256(
                        review_path.read_bytes(),
                    ).hexdigest(),
                )
        except ValueError as exc:
            return _failure(_CMD_BEGIN_REMEDIATION, str(exc))
    if phase == "probe":
        error = _commit_staged_evaluate_state(
            cycle_id,
            project_root,
            patch={"eval_phase": "remediation"},
        )
        if error is not None:
            return _failure(_CMD_BEGIN_REMEDIATION, error)
    dispatch = [
        dimension_id
        for dimension_id, status in dimensions.items()
        if status == "probed"
    ]
    return _success(
        _CMD_BEGIN_REMEDIATION,
        skip=not dispatch,
        dispatch=dispatch,
        dimension_dispatch=eval_data.get("dimension_dispatch", "parallel"),
        current_state=state["current_state"],
        eval_phase="remediation",
    )


def begin_dimension_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Create or resume one all-pending-Issue remediation context."""
    loaded = _remediation_command_context(
        _CMD_BEGIN_DIMENSION_REMEDIATION,
        cycle_id,
        project_root,
    )
    if isinstance(loaded, dict):
        loaded["dim"] = dim
        return loaded
    state, eval_data, evaluate_round, active_doc, paths = loaded
    blocked = _sync_committed_abandon_projection(
        cycle_id,
        project_root,
        command=_CMD_BEGIN_DIMENSION_REMEDIATION,
        state=state,
        eval_data=eval_data,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
        paths=paths,
        refuse_new_context=True,
        extra_failure={"dim": dim},
    )
    if blocked is not None:
        return blocked
    if eval_data.get("eval_phase") != "remediation":
        return _failure(
            _CMD_BEGIN_DIMENSION_REMEDIATION,
            "eval_phase must be 'remediation'",
            dim=dim,
        )
    try:
        dimension_id = _canonical_dim(cycle_id, project_root, dim)
    except ValueError as exc:
        return _failure(_CMD_BEGIN_DIMENSION_REMEDIATION, str(exc), dim=dim)
    dimension_status = parse_dimension_status(eval_data["dimension_status"])
    if dimension_status.get(dimension_id) not in {
        "probed",
        "remediating",
        "complete",
    }:
        return _failure(
            _CMD_BEGIN_DIMENSION_REMEDIATION,
            f"dimension is not probed: {dimension_id!r}",
            dim=dim,
        )
    review_path = _review_path_from_context(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
        dim=dimension_id,
    )
    try:
        rows = parse_review_file(
            review_path,
            expected_dimension_id=dimension_id,
            expected_round_token=eval_data["round_token"],
        )
    except ValueError as exc:
        return _failure(_CMD_BEGIN_DIMENSION_REMEDIATION, str(exc), dim=dim)
    operations = _operations_for_round(paths, eval_data["round_token"])
    probe_record = next(
        (
            record
            for record in operations
            if record.get("operation_kind") == "probe"
            and record.get("phase") == "committed"
            and record.get("dimension_id") == dimension_id
        ),
        None,
    )
    try:
        if probe_record is None:
            raise ValueError("missing committed probe operation")
        validate_review_against_probe_record(rows, probe_record)
    except ValueError as exc:
        return _failure(_CMD_BEGIN_DIMENSION_REMEDIATION, str(exc), dim=dim)
    pending = [
        row for row in rows
        if row.get("status", "").lower() == "pending"
    ]
    if not pending:
        try:
            validate_review_completion(
                rows=rows,
                dimension_id=dimension_id,
                remediation_records=operations,
                review_digest=hashlib.sha256(review_path.read_bytes()).hexdigest(),
            )
        except ValueError as exc:
            return _failure(_CMD_BEGIN_DIMENSION_REMEDIATION, str(exc), dim=dim)
        corpus = _load_corpus(cycle_id, project_root)

        def _complete_zero(data: dict[str, str]) -> dict[str, str]:
            updated = merge_current_dimension(
                data,
                dimension_id,
                "complete",
                corpus=corpus,
            )
            return _recompute_aggregate_counts(
                patch_issue_count(
                    updated,
                    dimension_id,
                    total=str(len(rows)),
                    resolved=str(count_resolved(rows)),
                ),
            )

        error = _commit_staged_evaluate_state(
            cycle_id,
            project_root,
            update=_complete_zero,
        )
        if error is not None:
            return _failure(_CMD_BEGIN_DIMENSION_REMEDIATION, error, dim=dim)
        return _success(
            _CMD_BEGIN_DIMENSION_REMEDIATION,
            dim=dim,
            skip=True,
        )
    if dimension_status.get(dimension_id) == "complete":
        return _failure(
            _CMD_BEGIN_DIMENSION_REMEDIATION,
            "complete dimension has pending Review findings",
            dim=dim,
        )

    required_issue_ids = [row["id"] for row in pending]
    handling_modes = {
        row["id"]: row["handling_mode"].lower()
        for row in pending
    }
    try:
        allowed_decisions = {
            row["id"]: allowed_decisions_for_issue(
                row["root_cause"],
                handling_modes[row["id"]],
            )
            for row in pending
        }
        expanded = _expanded_corpus(
            cycle_id,
            state,
            paths,
            evaluate_round,
            project_root=project_root,
        )
        dim_def = _dimension_def(expanded, dimension_id)
        operation_ctx = issue_remediation_context(
            operations_path=_operations_path(paths),
            write_staging_dir=Path(
                paths.get("write_staging_dir") or paths["evaluate_dir"],
            ),
            target_path=Path(str(dim_def["eval_target"]["path"])),
            review_path=review_path,
            round_token=eval_data["round_token"],
            dimension_id=dimension_id,
            method=dict(dim_def["method"]),
            sots=[dict(sot) for sot in dim_def["sots"]],
            required_issue_ids=required_issue_ids,
            handling_modes_by_issue=handling_modes,
            allowed_decisions_by_issue=allowed_decisions,
        )
    except (OSError, ValueError) as exc:
        return _failure(_CMD_BEGIN_DIMENSION_REMEDIATION, str(exc), dim=dim)

    corpus = _load_corpus(cycle_id, project_root)
    error = _commit_staged_evaluate_state(
        cycle_id,
        project_root,
        update=lambda data: merge_current_dimension(
            data,
            dimension_id,
            "remediating",
            corpus=corpus,
        ),
    )
    if error is not None:
        return _failure(
            _CMD_BEGIN_DIMENSION_REMEDIATION,
            f"projection_pending: {error}",
            dim=dim,
        )
    return _success(
        _CMD_BEGIN_DIMENSION_REMEDIATION,
        dim=dim,
        skip=False,
        operation_ctx=operation_ctx,
        dispatch_input=_format_remediation_dispatch_input(
            operation_ctx,
            pending,
        ),
    )


def cancel_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    operation_token: str,
) -> dict[str, Any]:
    """Cancel only a context-open remediation and release its persisted lease."""
    loaded = _remediation_command_context(
        _CMD_CANCEL_REMEDIATION,
        cycle_id,
        project_root,
    )
    if isinstance(loaded, dict):
        return loaded
    _state, eval_data, _evaluate_round, _active_doc, paths = loaded
    try:
        current = get_operation_record(_operations_path(paths), operation_token)
        if (
            current.get("operation_kind") != "remediation"
            or current.get("round_token") != eval_data["round_token"]
        ):
            raise ValueError("operation_token is not owned by this remediation round")
        cancelled = cancel_operation_record(
            _operations_path(paths),
            operation_token,
        )
    except ValueError as exc:
        return _failure(_CMD_CANCEL_REMEDIATION, str(exc))
    if cancelled.get("phase") == "cancelled":
        dimension_id = str(cancelled["dimension_id"])
        corpus = _load_corpus(cycle_id, project_root)
        error = _commit_staged_evaluate_state(
            cycle_id,
            project_root,
            update=lambda data: merge_current_dimension(
                data,
                dimension_id,
                "probed",
                corpus=corpus,
            ),
        )
        if error is not None:
            return _failure(
                _CMD_CANCEL_REMEDIATION,
                f"projection_pending: {error}",
            )
    return _success(
        _CMD_CANCEL_REMEDIATION,
        operation_token=operation_token,
        phase=cancelled["phase"],
        dimension_status="probed" if cancelled["phase"] == "cancelled" else None,
    )


def prepare_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    proposal_file: Path,
) -> dict[str, Any]:
    """Expose the read-only proposal validator through the Control API."""
    loaded = _remediation_command_context(
        _CMD_PREPARE_REMEDIATION,
        cycle_id,
        project_root,
    )
    if isinstance(loaded, dict):
        return loaded
    _state, eval_data, _evaluate_round, _active_doc, paths = loaded
    if eval_data.get("eval_phase") != "remediation":
        return _failure(_CMD_PREPARE_REMEDIATION, "eval_phase must be remediation")
    try:
        prepared = prepare_remediation_at(
            operations_path=_operations_path(paths),
            proposal_file=proposal_file,
        )
    except ValueError as exc:
        return _failure(_CMD_PREPARE_REMEDIATION, str(exc))
    return _success(_CMD_PREPARE_REMEDIATION, **prepared)


def _project_after_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    record: dict[str, Any],
    review_path: Path,
    eval_data: dict[str, str],
    idempotent: bool,
) -> dict[str, Any]:
    application = record.get("remediation_application")
    if not isinstance(application, dict):
        return _failure(
            _CMD_APPLY_REMEDIATION,
            "repair_required: committed remediation missing application",
        )
    outcome = str(application.get("final", {}).get("outcome") or "apply")
    dimension_id = str(record["dimension_id"])
    try:
        rows = parse_review_file(
            review_path,
            expected_dimension_id=dimension_id,
            expected_round_token=str(eval_data["round_token"]),
        )
    except ValueError as exc:
        return _failure(_CMD_APPLY_REMEDIATION, str(exc))
    pending = [row for row in rows if row.get("status") == "pending"]
    corpus = _load_corpus(cycle_id, project_root) or None

    def _project(data: dict[str, str]) -> dict[str, str]:
        updated = dict(data)
        if outcome == "abandon":
            updated["eval_status"] = "abandoned"
            updated["eval_phase"] = "done"
        else:
            next_status = "complete" if not pending else "remediating"
            updated = merge_current_dimension(
                updated,
                dimension_id,
                next_status,
                corpus=corpus,
            )
        updated = patch_issue_count(
            updated,
            dimension_id,
            total=str(len(rows)),
            resolved=str(count_resolved(rows)),
        )
        return _recompute_aggregate_counts(updated)

    error = _commit_staged_evaluate_state(cycle_id, project_root, update=_project)
    if error is not None:
        return _failure(
            _CMD_APPLY_REMEDIATION,
            f"projection_pending: {error}",
        )
    return _success(
        _CMD_APPLY_REMEDIATION,
        operation_token=record["operation_token"],
        outcome=outcome,
        target_effect=record.get("target_effect"),
        idempotent=idempotent,
        eval_status="abandoned" if outcome == "abandon" else eval_data.get("eval_status"),
    )


def apply_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    application_file: Path,
) -> dict[str, Any]:
    """Validate a RemediationApplication and commit the unified transaction."""
    loaded = _remediation_command_context(
        _CMD_APPLY_REMEDIATION,
        cycle_id,
        project_root,
    )
    if isinstance(loaded, dict):
        return loaded
    _state, eval_data, evaluate_round, active_doc, paths = loaded
    try:
        application = json.loads(application_file.read_text(encoding="utf-8"))
    except OSError as exc:
        return _failure(
            _CMD_APPLY_REMEDIATION,
            f"cannot read application file: {application_file}: {exc}",
        )
    except json.JSONDecodeError as exc:
        return _failure(
            _CMD_APPLY_REMEDIATION,
            f"invalid remediation application JSON: {exc}",
        )
    if not isinstance(application, dict) or not isinstance(application.get("proposal"), dict):
        return _failure(_CMD_APPLY_REMEDIATION, "application must embed a proposal")
    operation_token = application["proposal"].get("operation_token")
    if not isinstance(operation_token, str) or not operation_token:
        return _failure(
            _CMD_APPLY_REMEDIATION,
            "application proposal.operation_token must be non-empty",
        )
    operations_path = _operations_path(paths)
    try:
        record = get_operation_record(operations_path, operation_token)
    except ValueError as exc:
        return _failure(_CMD_APPLY_REMEDIATION, str(exc))
    if (
        record.get("operation_kind") != "remediation"
        or record.get("round_token") != eval_data["round_token"]
    ):
        return _failure(
            _CMD_APPLY_REMEDIATION,
            "operation_token is not owned by this remediation round",
        )
    review_path = _review_path_from_context(
        cycle_id,
        project_root,
        state=_state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
        dim=str(record["dimension_id"]),
    )
    phase = record.get("phase")
    if phase == "cancelled":
        return _failure(_CMD_APPLY_REMEDIATION, "cancelled operation cannot be applied")

    if phase in {"prepared", "target-applied", "review-applied", "committed"}:
        digest = application_submission_digest(
            record,
            canonicalize_remediation_application(record, application),
        )
        if digest != record.get("submission_digest"):
            return _failure(
                _CMD_APPLY_REMEDIATION,
                "conflict: different submission for operation_token",
            )
        if phase == "committed":
            return _project_after_remediation(
                cycle_id,
                project_root,
                record=record,
                review_path=review_path,
                eval_data=eval_data,
                idempotent=True,
            )
        recovered = _forward_recover_to_committed(
            cycle_id,
            project_root,
            command=_CMD_APPLY_REMEDIATION,
            operations_path=operations_path,
            record=record,
            paths=paths,
            review_path=review_path,
            evaluate_round=evaluate_round,
        )
        if not recovered.get("ok"):
            return recovered
        return _project_after_remediation(
            cycle_id,
            project_root,
            record=recovered["record"],
            review_path=review_path,
            eval_data=eval_data,
            idempotent=False,
        )
    if eval_data.get("eval_phase") != "remediation":
        return _failure(_CMD_APPLY_REMEDIATION, "eval_phase must be remediation")
    if phase != "context-open":
        return _failure(
            _CMD_APPLY_REMEDIATION,
            f"repair_required: unknown operation phase {phase!r}",
        )

    errors = validate_remediation_application(record, application)
    if errors:
        return _failure(
            _CMD_APPLY_REMEDIATION,
            f"remediation application invalid: {'; '.join(errors)}",
        )
    try:
        target_path = _target_path_from_record(record)
        live_target = _live_target_digest(cycle_id, project_root, target_path)
    except (OSError, ValueError) as exc:
        return _failure(_CMD_APPLY_REMEDIATION, str(exc))
    if live_target != record["target_base_digest"]:
        return _failure(
            _CMD_APPLY_REMEDIATION,
            "stale target: live digest does not match operation target_base_digest",
        )
    if not review_path.is_file():
        return _failure(_CMD_APPLY_REMEDIATION, "stale review: ReviewFile missing")
    before_content = review_path.read_text(encoding="utf-8")
    if _content_digest(before_content) != record["review_base_digest"]:
        return _failure(
            _CMD_APPLY_REMEDIATION,
            "stale review: live digest does not match operation review_base_digest",
        )

    canonical = canonicalize_remediation_application(record, application)
    final = canonical["final"]
    outcome = str(final["outcome"])
    updates = {
        str(entry["issue_id"]): (
            "resolved",
            str(entry["decision"]),
            str(entry["resolution"]),
        )
        for entry in final.get("resolutions", [])
        if isinstance(entry, dict)
    }
    after_content = _render_review_after(before_content, updates)
    review_errors = validate_review_content(after_content, phase="remediation")
    if review_errors:
        return _failure(
            _CMD_APPLY_REMEDIATION,
            f"generated review invalid: {'; '.join(review_errors)}",
        )

    target_effect = "none"
    target_after_digest = str(record["target_base_digest"])
    staged_path: str | None = None
    mutation = final.get("mutation")
    if outcome == "apply" and mutation is not None:
        snapshot_path = record.get("snapshot_path")
        if not isinstance(snapshot_path, str) or not snapshot_path:
            return _failure(_CMD_APPLY_REMEDIATION, "operation snapshot_path is missing")
        try:
            after_target = apply_unified_diff(
                Path(snapshot_path).read_text(encoding="utf-8"),
                str(mutation["unified_diff"]),
            )
        except ValueError as exc:
            return _failure(_CMD_APPLY_REMEDIATION, str(exc))
        if after_target == Path(snapshot_path).read_text(encoding="utf-8"):
            return _failure(
                _CMD_APPLY_REMEDIATION,
                "empty or no-op unified_diff is rejected",
            )
        target_after_digest = _content_digest(after_target)
        if target_after_digest == record["target_base_digest"]:
            return _failure(
                _CMD_APPLY_REMEDIATION,
                "empty or no-op unified_diff is rejected",
            )
        staged = Path(paths["write_staging_dir"]) / f"{operation_token}-target.staged"
        _atomic_write_text(staged, after_target)
        staged_path = staged.as_posix()
        target_effect = "mutation"

    prepared = {
        **record,
        "phase": "prepared",
        "submission_digest": application_submission_digest(record, canonical),
        "target_effect": target_effect,
        "target_after_digest": target_after_digest,
        "review_after_digest": _content_digest(after_content),
        "canonical_findings": None,
        "remediation_application": canonical,
        "review_before_content": before_content,
        "review_after_content": after_content,
        "target_staged_path": staged_path,
        "review_path": review_path.resolve().as_posix(),
    }
    try:
        record = _advance_phase(operations_path, prepared, "prepared")
    except ValueError as exc:
        return _failure(_CMD_APPLY_REMEDIATION, str(exc))
    recovered = _forward_recover_to_committed(
        cycle_id,
        project_root,
        command=_CMD_APPLY_REMEDIATION,
        operations_path=operations_path,
        record=record,
        paths=paths,
        review_path=review_path,
        evaluate_round=evaluate_round,
    )
    if not recovered.get("ok"):
        return recovered
    return _project_after_remediation(
        cycle_id,
        project_root,
        record=recovered["record"],
        review_path=review_path,
        eval_data=eval_data,
        idempotent=False,
    )


def restore_eval_target(
    cycle_id: str,
    project_root: Path,
    *,
    snapshot_path: Path,
    expected_current_digest: str,
    target_path: Path,
) -> dict[str, Any]:
    """CAS restore of one EvalTarget; refuses when live digest drifted."""
    del target_path
    paths = _paths_from_handoff() or {}
    result = _adapter().restore_eval_target(
        cycle_id,
        project_root,
        snapshot_path=snapshot_path,
        expected_current_digest=expected_current_digest,
        lease_id=str(paths.get("lease_id", "")),
    )
    if not result.get("ok"):
        return _failure(
            "restore-eval-target",
            str(result.get("error") or "restore_eval_target failed"),
        )
    return _success("restore-eval-target")


def check_dimension_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Derive one Dimension projection from Review v3 and v4 operations."""
    loaded = _remediation_command_context(
        _CMD_CHECK_DIMENSION_REMEDIATION,
        cycle_id,
        project_root,
    )
    if isinstance(loaded, dict):
        loaded["dim"] = dim
        return loaded
    state, eval_data, evaluate_round, active_doc, paths = loaded
    try:
        dimension_id = _canonical_dim(cycle_id, project_root, dim)
        review_path = _review_path_from_context(
            cycle_id,
            project_root,
            state=state,
            evaluate_round=evaluate_round,
            active_doc=active_doc,
            dim=dimension_id,
        )
        rows = parse_review_file(
            review_path,
            expected_dimension_id=dimension_id,
            expected_round_token=eval_data["round_token"],
        )
    except ValueError as exc:
        return _failure(_CMD_CHECK_DIMENSION_REMEDIATION, str(exc), dim=dim)
    pending = [row for row in rows if row.get("status") == "pending"]
    records = [
        record
        for record in _operations_for_round(paths, eval_data["round_token"])
        if record.get("operation_kind") == "remediation"
        and record.get("dimension_id") == dimension_id
    ]
    probe_record = next(
        (
            record
            for record in _operations_for_round(paths, eval_data["round_token"])
            if record.get("operation_kind") == "probe"
            and record.get("phase") == "committed"
            and record.get("dimension_id") == dimension_id
        ),
        None,
    )
    try:
        if probe_record is None:
            raise ValueError("missing committed probe operation")
        validate_review_against_probe_record(rows, probe_record)
    except ValueError as exc:
        return _failure(_CMD_CHECK_DIMENSION_REMEDIATION, str(exc), dim=dim)
    latest = records[-1] if records else None
    if not pending:
        try:
            validate_review_completion(
                rows=rows,
                dimension_id=dimension_id,
                remediation_records=records,
                review_digest=hashlib.sha256(review_path.read_bytes()).hexdigest(),
            )
        except ValueError as exc:
            return _failure(_CMD_CHECK_DIMENSION_REMEDIATION, str(exc), dim=dim)
        projected = "complete"
    elif latest is None or latest.get("phase") == "cancelled":
        projected = "probed"
    elif latest.get("phase") == "committed":
        if _application_outcome(latest) == "abandon":
            blocked = _project_abandoned_round(
                cycle_id,
                project_root,
                command=_CMD_CHECK_DIMENSION_REMEDIATION,
                eval_data=eval_data,
                record=latest,
                review_path=review_path,
                extra_failure={"dim": dim},
            )
            if blocked is not None:
                return blocked
            return _success(
                _CMD_CHECK_DIMENSION_REMEDIATION,
                dim=dim,
                dimension_status=parse_dimension_status(
                    eval_data["dimension_status"],
                ).get(dimension_id),
                pending_issue_ids=[row["id"] for row in pending],
                operation_phase=latest.get("phase"),
                eval_status="abandoned",
            )
        return _failure(
            _CMD_CHECK_DIMENSION_REMEDIATION,
            "repair_required: committed operation left pending issues",
            dim=dim,
        )
    else:
        projected = "remediating"
    corpus = _load_corpus(cycle_id, project_root)

    def _project(data: dict[str, str]) -> dict[str, str]:
        updated = merge_current_dimension(
            data,
            dimension_id,
            projected,
            corpus=corpus,
        )
        updated = patch_issue_count(
            updated,
            dimension_id,
            total=str(len(rows)),
            resolved=str(count_resolved(rows)),
        )
        return _recompute_aggregate_counts(updated)

    error = _commit_staged_evaluate_state(cycle_id, project_root, update=_project)
    if error is not None:
        return _failure(_CMD_CHECK_DIMENSION_REMEDIATION, error, dim=dim)
    return _success(
        _CMD_CHECK_DIMENSION_REMEDIATION,
        dim=dim,
        dimension_status=projected,
        pending_issue_ids=[row["id"] for row in pending],
        operation_phase=latest.get("phase") if latest else None,
    )


def remediation_complete(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Finish a full-remediation round only from Review and operation facts."""
    loaded = _remediation_command_context(
        _CMD_REMEDIATION_COMPLETE,
        cycle_id,
        project_root,
    )
    if isinstance(loaded, dict):
        return loaded
    state, eval_data, evaluate_round, active_doc, paths = loaded
    if eval_data.get("eval_phase") != "remediation":
        return _failure(_CMD_REMEDIATION_COMPLETE, "eval_phase must be remediation")
    status_by_dim = parse_dimension_status(eval_data["dimension_status"])
    dimensions = [
        dimension_id
        for dimension_id in _dispatch_canonical(cycle_id, project_root)
        if status_by_dim.get(dimension_id) != "skipped"
    ]
    operations = _operations_for_round(paths, eval_data["round_token"])
    probe_by_dimension = {
        str(record.get("dimension_id")): record
        for record in operations
        if record.get("operation_kind") == "probe"
        and record.get("phase") == "committed"
    }
    rows_by_dimension: dict[str, list[dict[str, str]]] = {}
    for dimension_id in dimensions:
        try:
            review_path = _review_path_from_context(
                cycle_id,
                project_root,
                state=state,
                evaluate_round=evaluate_round,
                active_doc=active_doc,
                dim=dimension_id,
            )
            rows = parse_review_file(
                review_path,
                expected_dimension_id=dimension_id,
                expected_round_token=eval_data["round_token"],
            )
            if dimension_id not in probe_by_dimension:
                raise ValueError("missing committed probe operation")
            validate_review_against_probe_record(
                rows,
                probe_by_dimension[dimension_id],
            )
            validate_review_completion(
                rows=rows,
                dimension_id=dimension_id,
                remediation_records=operations,
                review_digest=hashlib.sha256(review_path.read_bytes()).hexdigest(),
            )
            rows_by_dimension[dimension_id] = rows
        except ValueError as exc:
            return _failure(_CMD_REMEDIATION_COMPLETE, str(exc))
    pending_ids = [
        row["id"]
        for rows in rows_by_dimension.values()
        for row in rows
        if row.get("status") == "pending"
    ]
    if pending_ids:
        return _failure(
            _CMD_REMEDIATION_COMPLETE,
            f"pending findings remain: {pending_ids!r}",
        )
    if any(
        record.get("operation_kind") == "remediation"
        and record.get("phase") not in {"committed", "cancelled"}
        for record in operations
    ):
        return _failure(_CMD_REMEDIATION_COMPLETE, "open remediation operation remains")
    corpus = _load_corpus(cycle_id, project_root)

    def _finish(data: dict[str, str]) -> dict[str, str]:
        updated = dict(data)
        for dimension_id, rows in rows_by_dimension.items():
            updated = merge_current_dimension(
                updated,
                dimension_id,
                "complete",
                corpus=corpus,
            )
            updated = patch_issue_count(
                updated,
                dimension_id,
                total=str(len(rows)),
                resolved=str(count_resolved(rows)),
            )
        updated = _recompute_aggregate_counts(updated)
        updated["eval_phase"] = "done"
        updated["eval_status"] = "done"
        return updated

    error = _commit_staged_evaluate_state(cycle_id, project_root, update=_finish)
    if error is not None:
        return _failure(_CMD_REMEDIATION_COMPLETE, error)
    return _success(
        _CMD_REMEDIATION_COMPLETE,
        eval_phase="done",
        eval_status="done",
    )


def complete_probe_only(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Finish a probe-only round while preserving pending findings."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_COMPLETE_PROBE_ONLY
        return ctx
    state, _ws_path, eval_data, evaluate_round, active_doc, _mode = ctx
    if eval_data.get("eval_capability") != "probe-only":
        return _failure(
            _CMD_COMPLETE_PROBE_ONLY,
            "complete-probe-only requires probe-only capability",
        )
    dimensions = parse_dimension_status(eval_data["dimension_status"])
    active_dimensions = {
        dim_id: status
        for dim_id, status in dimensions.items()
        if status != "skipped"
    }
    terminal_replay = (
        eval_data.get("eval_phase") == "done"
        and eval_data.get("eval_status") == "done"
    )
    if not terminal_replay and eval_data.get("eval_phase") != "probe":
        return _failure(_CMD_COMPLETE_PROBE_ONLY, "eval_phase must be probe or done")
    if any(status not in {"probed", "complete"} for status in active_dimensions.values()):
        return _failure(
            _CMD_COMPLETE_PROBE_ONLY,
            "not all dimensions are probed",
        )
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=_evaluate_state_path(cycle_id, project_root),
    )
    operations = _operations_for_round(paths, eval_data["round_token"])
    if any(
        record.get("operation_kind") == "probe"
        and record.get("phase") != "committed"
        for record in operations
    ):
        return _failure(_CMD_COMPLETE_PROBE_ONLY, "open probe operation remains")
    committed_probe_dimensions = {
        str(record.get("dimension_id"))
        for record in operations
        if record.get("operation_kind") == "probe"
        and record.get("phase") == "committed"
    }
    if not set(active_dimensions) <= committed_probe_dimensions:
        return _failure(
            _CMD_COMPLETE_PROBE_ONLY,
            "missing committed probe operation for one or more dimensions",
        )
    rows_by_dimension: dict[str, list[dict[str, str]]] = {}
    review_paths: list[str] = []
    for dimension_id in active_dimensions:
        review_path = _review_path_from_context(
            cycle_id,
            project_root,
            state=state,
            evaluate_round=evaluate_round,
            active_doc=active_doc,
            dim=dimension_id,
        )
        if not review_path.is_file():
            return _failure(
                _CMD_COMPLETE_PROBE_ONLY,
                f"ReviewFile missing for dimension {dimension_id!r}",
            )
        try:
            rows_by_dimension[dimension_id] = parse_review_file(
                review_path,
                expected_dimension_id=dimension_id,
                expected_round_token=eval_data["round_token"],
            )
        except ValueError as exc:
            return _failure(_CMD_COMPLETE_PROBE_ONLY, str(exc))
        review_paths.append(review_path.as_posix())
    try:
        issues = canonical_probe_findings_from_reviews(
            rows_by_dimension,
            operations,
            expected_dimensions=list(active_dimensions),
        )
    except ValueError as exc:
        return _failure(_CMD_COMPLETE_PROBE_ONLY, str(exc))
    if terminal_replay:
        return _success(
            _CMD_COMPLETE_PROBE_ONLY,
            eval_phase="done",
            eval_status="done",
            idempotent=True,
            issues=issues,
            review_paths=review_paths,
        )
    corpus = _load_corpus(cycle_id, project_root)

    def _finish(data: dict[str, str]) -> dict[str, str]:
        updated = dict(data)
        for dimension_id in active_dimensions:
            updated = merge_current_dimension(
                updated,
                dimension_id,
                "complete",
                corpus=corpus,
            )
        updated["eval_phase"] = "done"
        updated["eval_status"] = "done"
        return updated

    error = _commit_staged_evaluate_state(cycle_id, project_root, update=_finish)
    if error is not None:
        return _failure(_CMD_COMPLETE_PROBE_ONLY, error)
    return _success(
        _CMD_COMPLETE_PROBE_ONLY,
        eval_phase="done",
        eval_status="done",
        idempotent=False,
        issues=issues,
        review_paths=review_paths,
    )




def _format_remediation_dispatch_input(
    operation_ctx: dict[str, Any],
    pending_issues: list[dict[str, str]],
) -> str:
    lines = [
        f"ROUND_TOKEN: {operation_ctx['round_token']}",
        f"OPERATION_TOKEN: {operation_ctx['operation_token']}",
        f"DIMENSION_ID: {operation_ctx['dimension_id']}",
        f"OPERATION_KIND: {operation_ctx['operation_kind']}",
        f"TARGET_BASE_DIGEST: {operation_ctx['target_base_digest']}",
        f"REVIEW_BASE_DIGEST: {operation_ctx['review_base_digest']}",
        f"ALLOWED_SUBMISSION: {operation_ctx['allowed_submission']}",
        "RESOLVED_METHOD: "
        + json.dumps(operation_ctx["resolved_method"], ensure_ascii=False),
        "RESOLVED_SOTS: "
        + json.dumps(operation_ctx["resolved_sots"], ensure_ascii=False),
        "PENDING_ISSUES: " + json.dumps(pending_issues, ensure_ascii=False),
        "REQUIRED_ISSUE_IDS: "
        + json.dumps(operation_ctx["required_issue_ids"], ensure_ascii=False),
        "HANDLING_MODES_BY_ISSUE: "
        + json.dumps(
            operation_ctx["handling_modes_by_issue"],
            ensure_ascii=False,
        ),
        "ALLOWED_DECISIONS_BY_ISSUE: "
        + json.dumps(
            operation_ctx["allowed_decisions_by_issue"],
            ensure_ascii=False,
        ),
    ]
    return "\n".join(lines)


def _review_rows_for_dim(
    cycle_id: str,
    project_root: Path,
    *,
    state: dict[str, str],
    evaluate_round: int,
    active_doc: int,
    dim: str,
) -> list[dict[str, str]]:
    review_path = _review_path_from_context(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
        dim=dim,
    )
    return parse_review_file(review_path)

























def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload.get("ok") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="lulu-dev-workflow eval control")
    parser.add_argument(
        "--workflow",
        required=False,
        default="",
        help="Internal workflow label set by eval_entry from adapter config",
    )
    parser.add_argument("--cycle-id", required=True, help="Cycle ID")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
        help="Project root directory",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        _CMD_INIT_ROUND,
        help="Initialize evaluate-state.md (internal; session_control)",
    )

    sub.add_parser(
        _CMD_BEGIN_EVAL_ROUND,
        help="Enter focus evaluating and return eval loop payload",
    )

    begin_parser = sub.add_parser(
        _CMD_BEGIN_DIMENSION,
        help="Begin a single eval dimension",
    )
    begin_parser.add_argument(
        "--dim",
        required=True,
        help="Dimension dispatch key (legacy e1/e2/e3 or canonical id)",
    )

    snapshot_parser = sub.add_parser(
        _CMD_READ_B_SNAPSHOT,
        help="Read a token-authorized EvalTarget B snapshot",
    )
    snapshot_parser.add_argument(
        "--dimension-token",
        "--operation-token",
        dest="dimension_token",
        required=True,
    )

    evidence_snapshot_parser = sub.add_parser(
        _CMD_READ_EVIDENCE_SNAPSHOT,
        help="Read token-authorized dynamic SoT evidence",
    )
    evidence_snapshot_parser.add_argument(
        "--dimension-token",
        "--operation-token",
        dest="dimension_token",
        required=True,
    )
    evidence_snapshot_parser.add_argument("--evidence-ref", required=True)

    submit_probe_parser = sub.add_parser(
        _CMD_SUBMIT_PROBE_FINDINGS,
        help="Validate and publish a token-scoped probe finding payload",
    )
    submit_probe_parser.add_argument(
        "--payload-file",
        type=Path,
        required=True,
        help="JSON payload containing dimension_token and findings",
    )
    check_parser = sub.add_parser(
        _CMD_CHECK_DIMENSION,
        help="Read single-dimension outcome after dimension-probe-runner",
    )
    check_parser.add_argument(
        "--dim",
        required=True,
        help="Dimension dispatch key (legacy e1/e2/e3 or canonical id)",
    )

    sub.add_parser(
        _CMD_BEGIN_REMEDIATION,
        help="Return unified remediation dispatch list or skip",
    )
    begin_remediation_dim = sub.add_parser(
        _CMD_BEGIN_DIMENSION_REMEDIATION,
        help="Begin unified remediation for one dimension",
    )
    begin_remediation_dim.add_argument("--dim", required=True)
    cancel_remediation_parser = sub.add_parser(
        _CMD_CANCEL_REMEDIATION,
        help="Cancel a context-open remediation operation",
    )
    cancel_remediation_parser.add_argument("--operation-token", required=True)
    prepare_remediation_parser = sub.add_parser(
        _CMD_PREPARE_REMEDIATION,
        help="Read-only validate a remediation proposal",
    )
    prepare_remediation_parser.add_argument(
        "--proposal-file",
        type=Path,
        required=True,
        help="Candidate RemediationProposal JSON",
    )
    apply_remediation_parser = sub.add_parser(
        _CMD_APPLY_REMEDIATION,
        help="Validate and commit a RemediationApplication transaction",
    )
    apply_remediation_parser.add_argument(
        "--application-file",
        type=Path,
        required=True,
        help="Final RemediationApplication JSON",
    )
    check_remediation_dim = sub.add_parser(
        _CMD_CHECK_DIMENSION_REMEDIATION,
        help="Check unified remediation for one dimension",
    )
    check_remediation_dim.add_argument("--dim", required=True)
    sub.add_parser(
        _CMD_REMEDIATION_COMPLETE,
        help="Complete a full-remediation round",
    )
    sub.add_parser(
        _CMD_COMPLETE_PROBE_ONLY,
        help="Complete a probe-only round with pending findings",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def run_eval(
    args: argparse.Namespace,
    adapter: WorkflowAdapter,
    *,
    handoff: dict[str, Any] | None = None,
) -> int:
    """Run eval subcommand with an injected WorkflowAdapter (stage entrypoint)."""
    project_root = args.project_root.resolve()
    cycle_id = args.cycle_id.strip()
    adapter_token = _ADAPTER_CTX.set(adapter)
    workflow_token = _WORKFLOW_ID_CTX.set(args.workflow.strip())
    handoff_token = _HANDOFF_CTX.set(handoff)

    try:
        if args.command == _CMD_INIT_ROUND:
            return _emit(init_round(cycle_id, project_root))
        if args.command == _CMD_BEGIN_EVAL_ROUND:
            return _emit(begin_eval_round(cycle_id, project_root))
        if args.command == _CMD_BEGIN_DIMENSION:
            payload = begin_dimension(cycle_id, project_root, dim=args.dim)
            if payload.get("ok") and "dispatch_input" in payload:
                print(payload["dispatch_input"])
                return 0
            return _emit(payload)
        if args.command == _CMD_READ_B_SNAPSHOT:
            return _emit(
                read_b_snapshot_cmd(
                    cycle_id,
                    project_root,
                    dimension_token=args.dimension_token,
                ),
            )
        if args.command == _CMD_READ_EVIDENCE_SNAPSHOT:
            return _emit(
                read_evidence_snapshot_cmd(
                    cycle_id,
                    project_root,
                    dimension_token=args.dimension_token,
                    evidence_ref=args.evidence_ref,
                ),
            )
        if args.command == _CMD_SUBMIT_PROBE_FINDINGS:
            return _emit(
                submit_probe_findings(
                    cycle_id,
                    project_root,
                    payload_file=args.payload_file,
                ),
            )
        if args.command == _CMD_CHECK_DIMENSION:
            return _emit(check_dimension(cycle_id, project_root, dim=args.dim))
        if args.command == _CMD_BEGIN_REMEDIATION:
            return _emit(begin_remediation(cycle_id, project_root))
        if args.command == _CMD_BEGIN_DIMENSION_REMEDIATION:
            payload = begin_dimension_remediation(
                cycle_id,
                project_root,
                dim=args.dim,
            )
            if payload.get("ok") and "dispatch_input" in payload:
                print(payload["dispatch_input"])
                return 0
            return _emit(payload)
        if args.command == _CMD_CANCEL_REMEDIATION:
            return _emit(
                cancel_remediation(
                    cycle_id,
                    project_root,
                    operation_token=args.operation_token,
                ),
            )
        if args.command == _CMD_PREPARE_REMEDIATION:
            return _emit(
                prepare_remediation(
                    cycle_id,
                    project_root,
                    proposal_file=args.proposal_file,
                ),
            )
        if args.command == _CMD_APPLY_REMEDIATION:
            return _emit(
                apply_remediation(
                    cycle_id,
                    project_root,
                    application_file=args.application_file,
                ),
            )
        if args.command == _CMD_CHECK_DIMENSION_REMEDIATION:
            return _emit(
                check_dimension_remediation(
                    cycle_id,
                    project_root,
                    dim=args.dim,
                ),
            )
        if args.command == _CMD_REMEDIATION_COMPLETE:
            return _emit(remediation_complete(cycle_id, project_root))
        if args.command == _CMD_COMPLETE_PROBE_ONLY:
            return _emit(complete_probe_only(cycle_id, project_root))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        _ADAPTER_CTX.reset(adapter_token)
        _WORKFLOW_ID_CTX.reset(workflow_token)
        _HANDOFF_CTX.reset(handoff_token)

    return 1


def main() -> int:
    print(
        "错误：请通过 eval_entry.py 调用（例如 "
        "python3 eval_entry.py --adapter-config-file <json> ...）。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
