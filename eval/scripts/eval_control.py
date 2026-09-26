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
import json
import os
import sys
from contextvars import ContextVar
from pathlib import Path
from typing import Any

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


def begin_eval_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Enter focus evaluating or start next eval round; return payload."""
    import round_control
    return round_control.begin_eval_round(cycle_id, project_root)


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
