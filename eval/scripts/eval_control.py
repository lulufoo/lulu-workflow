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
    read-unit-view              Read token-authorized EvalTarget B unit view
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
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Callable

_EVAL_LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(_EVAL_LIB))
from eval_path import ensure_eval_script_layers  # noqa: E402

ensure_eval_script_layers()

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

from evaluate_state_binding import (  # noqa: E402
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
    from evaluate_state_binding import dispatch_dims_for_corpus

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
_CMD_READ_UNIT_VIEW = "read-unit-view"
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


def begin_eval_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Enter focus evaluating or start next eval round; return payload."""
    import round_control
    return round_control.begin_eval_round(cycle_id, project_root)

def _operations_path(paths: dict[str, str]) -> Path:
    """Return the Script-owned runtime record path for this Eval round."""
    return Path(paths["evaluate_dir"]) / "eval-operations.json"


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
    import round_control
    return round_control.init_round(cycle_id, project_root, mode=mode)

def begin_dimension(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Mark a dimension in progress and return dimension-probe-runner input."""
    import probe_control
    return probe_control.begin_dimension(cycle_id, project_root, dim=dim)


def read_b_snapshot_cmd(
    cycle_id: str,
    project_root: Path,
    *,
    dimension_token: str,
) -> dict[str, Any]:
    """Return a token-authorized read-only snapshot of EvalTarget B."""
    import probe_control
    return probe_control.read_b_snapshot_cmd(
        cycle_id,
        project_root,
        dimension_token=dimension_token,
    )


def read_unit_view_cmd(
    cycle_id: str,
    project_root: Path,
    *,
    dimension_token: str,
) -> dict[str, Any]:
    """Return chapter units from the token-authorized EvalTarget B."""
    import probe_control
    return probe_control.read_unit_view_cmd(
        cycle_id,
        project_root,
        dimension_token=dimension_token,
    )


def read_evidence_snapshot_cmd(
    cycle_id: str,
    project_root: Path,
    *,
    dimension_token: str,
    evidence_ref: str,
) -> dict[str, Any]:
    """Return token-authorized dynamic SoT evidence content."""
    import probe_control
    return probe_control.read_evidence_snapshot_cmd(
        cycle_id,
        project_root,
        dimension_token=dimension_token,
        evidence_ref=evidence_ref,
    )


def _load_probe_payload(path: Path) -> tuple[dict[str, Any], str]:
    """Load and normalize the minimal token-scoped probe submission payload."""
    import probe_control
    return probe_control._load_probe_payload(path)




def prepare_remediation_at(
    *,
    operations_path: Path,
    proposal_file: Path,
) -> dict[str, Any]:
    """Validate and canonicalize a proposal without writing any Eval-owned file."""
    import remediation_control
    return remediation_control.prepare_remediation_at(
        operations_path=operations_path,
        proposal_file=proposal_file,
    )

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
    import probe_control
    return probe_control._render_probe_review(
        dimension_label=dimension_label,
        dimension_id=dimension_id,
        round_token=round_token,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        method_focus=method_focus,
        handling_policy=handling_policy,
        findings=findings,
    )


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
    import probe_control
    return probe_control.submit_probe_findings(
        cycle_id,
        project_root,
        payload_file=payload_file,
    )


def check_dimension(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Read-only verify a dimension after dimension-probe-runner."""
    import probe_control
    return probe_control.check_dimension(cycle_id, project_root, dim=dim)


def _remediation_command_context(
    command: str,
    cycle_id: str,
    project_root: Path,
):
    """Load common full-remediation command state and paths."""
    import remediation_control
    return remediation_control._remediation_command_context(
        command,
        cycle_id,
        project_root,
    )


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
    import remediation_control
    return remediation_control.begin_remediation(cycle_id, project_root)

def begin_dimension_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Create or resume one all-pending-Issue remediation context."""
    import remediation_control
    return remediation_control.begin_dimension_remediation(
        cycle_id,
        project_root,
        dim=dim,
    )

def cancel_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    operation_token: str,
) -> dict[str, Any]:
    """Cancel only a context-open remediation and release its persisted lease."""
    import remediation_control
    return remediation_control.cancel_remediation(
        cycle_id,
        project_root,
        operation_token=operation_token,
    )

def prepare_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    proposal_file: Path,
) -> dict[str, Any]:
    """Expose the read-only proposal validator through the Control API."""
    import remediation_control
    return remediation_control.prepare_remediation(
        cycle_id,
        project_root,
        proposal_file=proposal_file,
    )

def apply_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    application_file: Path,
) -> dict[str, Any]:
    """Validate a RemediationApplication and commit the unified transaction."""
    import remediation_control
    return remediation_control.apply_remediation(
        cycle_id,
        project_root,
        application_file=application_file,
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
    import remediation_control
    return remediation_control.restore_eval_target(
        cycle_id,
        project_root,
        snapshot_path=snapshot_path,
        expected_current_digest=expected_current_digest,
        target_path=target_path,
    )

def check_dimension_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Derive one Dimension projection from Review v3 and v4 operations."""
    import remediation_control
    return remediation_control.check_dimension_remediation(
        cycle_id,
        project_root,
        dim=dim,
    )

def remediation_complete(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Finish a full-remediation round only from Review and operation facts."""
    import remediation_control
    return remediation_control.remediation_complete(cycle_id, project_root)

def complete_probe_only(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Finish a probe-only round while preserving pending findings."""
    import round_control
    return round_control.complete_probe_only(cycle_id, project_root)


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

    unit_view_parser = sub.add_parser(
        _CMD_READ_UNIT_VIEW,
        help="Read token-authorized EvalTarget B unit view",
    )
    unit_view_parser.add_argument(
        "--dimension-token",
        "--operation-token",
        dest="dimension_token",
        required=True,
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
        if args.command == _CMD_READ_UNIT_VIEW:
            return _emit(
                read_unit_view_cmd(
                    cycle_id,
                    project_root,
                    dimension_token=args.dimension_token,
                ),
            )
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
