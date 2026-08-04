#!/usr/bin/env python3
"""Eval control for lulu-dev-workflow eval domain.

Owns mechanical writes to evaluate-state.md. Workflow-specific paths and state
transitions go through an injected WorkflowAdapter, loaded per-profile by
eval_entry.py (dynamic ``profile.eval.adapter_module`` / ``adapter_class``
loading, mirrors start.py's StartAdapter loading).

Invoke via eval_entry.py with caller-supplied adapter config
(e.g. `--adapter-config-file <json>`). Do not run this module as __main__.

Subcommands:
    init-round                  Initialize evaluate-state.md (internal; session_control)
    begin-eval-round            Enter focus evaluating (session stays Working) or next round
    begin-dimension             Mark dimension in_progress and return eval-runner inputs
    read-b-snapshot             Read token-authorized EvalTarget B content
    read-evidence-snapshot      Read token-authorized dynamic SoT evidence
    submit-probe-findings       Validate and publish token-scoped probe findings
    submit-remediation-diff     Validate and publish token-scoped remediation diff
    check-dimension             Read-only verify dimension probed after eval-runner
    probe-complete              Sum issues; advance fix_phase to artifact-remediation
    begin-artifact-remediation       Return artifact remediation dispatch list or skip
    begin-dimension-artifact-remediation  Per-dim artifact runner input (plain text)
    check-dimension-artifact-remediation  Reconcile one dim after artifact runner
    artifact-remediation-complete    Advance fix_phase to done
    begin-human-resolution           Return Human Resolution dispatch list or skip
    begin-dimension-human-resolution Per-dim Human Resolution context
    submit-human-resolution          Validate and publish a human resolution payload
    check-dimension-human-resolution Reconcile one dimension after Human Resolution
    human-resolution-complete        Advance to Artifact Remediation or abandon
    complete-round              Finalize evaluate-state and return summary payload
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
    has_escalated,
    parse_review_file,
    pending_artifact_rows,
    pending_human_rows,
)
from review_schema import validate_review_content, validate_review_file  # noqa: E402
from corpus_schema import (  # noqa: E402
    expand_corpus,
    resolve_dim_id,
)
from evaluate_state_schema import (  # noqa: E402
    all_dims_at_least,
    is_v5_state,
    load_evaluate_state,
    parse_dimension_status,
    parse_dimension_tokens,
    parse_issue_counts,
    patch_issue_count,
    save_evaluate_state,
    sum_issue_totals,
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
    close_operation,
    close_probe_operation,
    get_operation_record,
)
from unified_diff import apply_unified_diff  # noqa: E402

_ADAPTER_CTX: ContextVar[WorkflowAdapter | None] = ContextVar("workflow_adapter", default=None)
_WORKFLOW_ID_CTX: ContextVar[str | None] = ContextVar("workflow_id", default=None)
_HANDOFF_CTX: ContextVar[dict[str, Any] | None] = ContextVar("eval_handoff", default=None)


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
    """Resolve session EvalCorpus via workflow adapter."""
    return _adapter().resolve_eval_corpus(cycle_id, project_root)


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
            if state is not None:
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
_CMD_SUBMIT_REMEDIATION_DIFF = "submit-remediation-diff"
_CMD_CHECK_DIMENSION = "check-dimension"
_CMD_PROBE_COMPLETE = "probe-complete"
_CMD_BEGIN_ARTIFACT_REMEDIATION = "begin-artifact-remediation"
_CMD_BEGIN_DIMENSION_ARTIFACT = "begin-dimension-artifact-remediation"
_CMD_CHECK_DIMENSION_ARTIFACT = "check-dimension-artifact-remediation"
_CMD_ARTIFACT_REMEDIATION_COMPLETE = "artifact-remediation-complete"
_CMD_BEGIN_HUMAN_RESOLUTION = "begin-human-resolution"
_CMD_BEGIN_DIMENSION_HUMAN = "begin-dimension-human-resolution"
_CMD_SUBMIT_HUMAN_RESOLUTION = "submit-human-resolution"
_CMD_CHECK_DIMENSION_HUMAN = "check-dimension-human-resolution"
_CMD_HUMAN_RESOLUTION_COMPLETE = "human-resolution-complete"
_CMD_COMPLETE_ROUND = "complete-round"

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


_ENTRY_V5_KEYS = (
    "version",
    "eval_status",
    "fix_phase",
    "dimension_status",
    "corpus_ref",
    "corpus_fingerprint",
    "dimension_dispatch",
)
_EXPECTED_SESSION_STATE = "Working"
_EXPECTED_FOCUS_PHASE = "evaluating"
_VALID_MODES = frozenset({"product", "tech"})
_SEVERITY_RANK = {"critical": 3, "medium": 2, "minor": 1}
_PROBE_PAYLOAD_KEYS = frozenset({"dimension_token", "findings"})
_REMEDIATION_PAYLOAD_KEYS = frozenset(
    {"dimension_token", "base_digest", "unified_diff", "issue_ids"},
)
_HUMAN_RESOLUTION_PAYLOAD_KEYS = frozenset(
    {
        "dimension_token",
        "base_digest",
        "issue_ids",
        "resolution_kind",
        "resolution",
    },
)
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


def _success(command: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": True, "command": command}
    payload.update(extra)
    return payload


def _failure(command: str, reason: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"ok": False, "command": command, "reason": reason}
    payload.update(extra)
    return payload


def _validate_evaluate_state_for_session(
    eval_data: dict[str, str],
    cycle_id: str,
    project_root: Path,
) -> str | None:
    """Return error reason when evaluate-state does not match session at entry."""
    if not is_v5_state(eval_data):
        return "evaluate-state is not v5; start a new Eval round."
    if eval_data.get("phase") != "evaluate":
        return f"phase is {eval_data.get('phase')!r}, expected 'evaluate'."
    try:
        expected = build_initial_evaluate_state_for_corpus(
            _load_corpus(cycle_id, project_root),
            cycle_type=_adapter().detect_cycle_type(cycle_id),
        )
    except ValueError as exc:
        return str(exc)
    for key in _ENTRY_V5_KEYS:
        actual = eval_data.get(key)
        exp = expected.get(key)
        if actual != exp:
            return (
                f"{key} is {actual!r}, expected {exp!r} "
                f"for this session."
            )
    return None


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
        return f"{issue_id}: {description}"
    return description or issue_id


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

    try:
        eval_data = load_evaluate_state(es_path)
    except ValueError as exc:
        return _failure("", str(exc), current_state=current)

    if not is_v5_state(eval_data):
        return _failure(
            "",
            "evaluate-state must be v5; start a new eval round.",
            current_state=current,
        )

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
    """Allocate next per-L (or legacy) round, re-init evaluate-state, return payload."""
    del ws_path, state
    try:
        handoff = _refresh_handoff(cycle_id, project_root, require_evaluating=True)
    except ValueError as exc:
        return _failure(_CMD_BEGIN_EVAL_ROUND, str(exc))
    context = handoff["context"]
    evaluate_round = int(context["evaluate_round"])
    formal_es = Path(str(context["evaluate_state_path"]))

    corpus = _load_corpus(cycle_id, project_root)
    cycle_type = _adapter().detect_cycle_type(cycle_id)
    next_state = build_initial_evaluate_state_for_corpus(
        corpus,
        cycle_type=cycle_type,
        evaluate_round=evaluate_round,
        focus_l=str(context.get("session_key", "")),
    )
    error = _commit_staged_evaluate_state(
        cycle_id,
        project_root,
        state=next_state,
        previous_done_required=formal_es.is_file(),
    )
    if error is not None:
        return _failure(
            _CMD_BEGIN_EVAL_ROUND,
            error,
        )
    del mode
    return build_eval_loop_payload(cycle_id, project_root)


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
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                "evaluate-state.md not found.",
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

        if not is_v5_state(eval_data):
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                "evaluate-state must be v5; start a new eval round.",
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
        return build_eval_loop_payload(cycle_id, project_root)

    entry = _adapter().enter_evaluating(cycle_id, project_root)
    if not entry.get("ok"):
        resume = entry.get("resume", {})
        return _failure(
            _CMD_BEGIN_EVAL_ROUND,
            resume.get("action")
            or (
                f"cannot enter evaluating from state "
                f"{entry.get('current_state', '')!r}."
            ),
            current_state=entry.get("current_state", ""),
        )

    try:
        _refresh_handoff(cycle_id, project_root, require_evaluating=True)
    except ValueError as exc:
        return _failure(
            _CMD_BEGIN_EVAL_ROUND,
            str(exc),
            current_state=_EXPECTED_SESSION_STATE,
        )

    state = _adapter().load_workflow_state(cycle_id, project_root)
    mode = state["mode"]
    es_path = _evaluate_state_path(cycle_id, project_root)
    if not es_path.exists() or entry.get("transitioned"):
        init_round(cycle_id, project_root, mode=mode)

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
    """Initialize evaluate-state.md for the current active revision / L."""
    if mode is None:
        mode = _adapter().load_workflow_state(cycle_id, project_root)["mode"]
    if _handoff_context() is None:
        try:
            _refresh_handoff(cycle_id, project_root, require_evaluating=False)
        except ValueError as exc:
            return _failure(_CMD_INIT_ROUND, str(exc))
    es_path = _evaluate_state_path(cycle_id, project_root)
    corpus = _load_corpus(cycle_id, project_root)
    cycle_type = _adapter().detect_cycle_type(cycle_id)
    context = _handoff_context() or {}
    evaluate_round = None
    session_key = ""
    if context:
        try:
            evaluate_round = int(context.get("evaluate_round", 0)) or None
        except (TypeError, ValueError):
            evaluate_round = None
        session_key = str(context.get("session_key", ""))
    initial_state = build_initial_evaluate_state_for_corpus(
        corpus,
        cycle_type=cycle_type,
        evaluate_round=evaluate_round,
        focus_l=session_key,
    )
    error = _commit_staged_evaluate_state(
        cycle_id,
        project_root,
        state=initial_state,
        set_phase_evaluating=True,
    )
    if error is not None:
        return _failure(_CMD_INIT_ROUND, error)
    return _success(
        _CMD_INIT_ROUND,
        mode=mode,
        path=es_path.resolve().as_posix(),
        evaluate_round=evaluate_round,
        session_key=session_key,
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

    if eval_data.get("fix_phase") != "probe":
        return _failure(
            _CMD_BEGIN_DIMENSION,
            f"fix_phase is {eval_data.get('fix_phase')!r}, expected 'probe'.",
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
        updated = merge_current_dimension(data, dim, "in_progress", corpus=corpus)
        dimension_tokens = parse_dimension_tokens(updated["dimension_tokens"])
        dimension_tokens[canonical_dim] = operation_ctx["dimension_token"]
        updated["dimension_tokens"] = json.dumps(
            dimension_tokens,
            separators=(",", ":"),
        )
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


def _load_remediation_payload(path: Path) -> tuple[dict[str, Any], str]:
    """Load the minimal, token-scoped remediation diff payload."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read payload file: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid remediation payload JSON: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != _REMEDIATION_PAYLOAD_KEYS:
        raise ValueError(
            "remediation payload must contain only dimension_token, base_digest, "
            "unified_diff, and issue_ids",
        )
    for field in ("dimension_token", "base_digest", "unified_diff"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            raise ValueError(f"remediation payload {field} must be a non-empty string")
    base_digest = str(payload["base_digest"])
    if len(base_digest) != 64 or any(char not in "0123456789abcdef" for char in base_digest):
        raise ValueError("remediation payload base_digest must be a SHA-256 hex digest")
    issue_ids = payload.get("issue_ids")
    if (
        not isinstance(issue_ids, list)
        or not issue_ids
        or any(not isinstance(issue_id, str) or not issue_id for issue_id in issue_ids)
        or len(set(issue_ids)) != len(issue_ids)
    ):
        raise ValueError("remediation payload issue_ids must be unique non-empty strings")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return payload, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_human_resolution_payload(path: Path) -> tuple[dict[str, Any], str]:
    """Load the minimal, token-scoped Human Resolution payload."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read payload file: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid human resolution payload JSON: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != _HUMAN_RESOLUTION_PAYLOAD_KEYS:
        raise ValueError(
            "human resolution payload must contain only dimension_token, "
            "base_digest, issue_ids, resolution_kind, and resolution",
        )
    for field in ("dimension_token", "base_digest", "resolution_kind", "resolution"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise ValueError(
                f"human resolution payload {field} must be a non-empty string",
            )
    if "\n" in payload["resolution"] or "|" in payload["resolution"]:
        raise ValueError("human resolution payload resolution must be one table cell")
    if payload["resolution_kind"] not in {"select", "allow-multiple", "escalate"}:
        raise ValueError(
            "human resolution payload resolution_kind must be select, "
            "allow-multiple, or escalate",
        )
    base_digest = str(payload["base_digest"])
    if len(base_digest) != 64 or any(char not in "0123456789abcdef" for char in base_digest):
        raise ValueError(
            "human resolution payload base_digest must be a SHA-256 hex digest",
        )
    issue_ids = payload.get("issue_ids")
    if (
        not isinstance(issue_ids, list)
        or not issue_ids
        or any(not isinstance(issue_id, str) or not issue_id for issue_id in issue_ids)
        or len(set(issue_ids)) != len(issue_ids)
    ):
        raise ValueError(
            "human resolution payload issue_ids must be unique non-empty strings",
        )
    if payload["resolution_kind"] == "select" and len(issue_ids) != 1:
        raise ValueError("select resolution requires exactly one issue id")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return payload, hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _remediation_rows(
    rows: list[dict[str, str]],
    *,
    issue_ids: list[str],
    operation_kind: str,
) -> str | None:
    """Validate that a diff resolves only pending rows authorized by its token."""
    by_id = {row.get("id", ""): row for row in rows}
    if len(by_id) != len(rows):
        return "review contains duplicate issue ids"
    if operation_kind != "artifact-remediation":
        return f"invalid remediation operation kind: {operation_kind}"
    expected = {"WO-MISS", "WO-ERROR"}
    for issue_id in issue_ids:
        row = by_id.get(issue_id)
        if row is None:
            return f"issue id is not in this dimension review: {issue_id}"
        if row.get("status", "").lower() != "pending":
            return f"issue id is not pending: {issue_id}"
        root_cause = row.get("root_cause", "").upper()
        if root_cause == "SOT-DEFECT":
            return "SOT-DEFECT requires escalation; B mutation is not authorized"
        if root_cause not in expected:
            return f"issue id is not authorized for {operation_kind}: {issue_id}"
    return None


def _render_remediated_review(
    content: str,
    *,
    issue_ids: list[str],
    operation_kind: str,
) -> str:
    """Change only selected review dispositions while preserving all other text."""
    lines = content.splitlines(keepends=True)
    header: list[str] | None = None
    selected = set(issue_ids)
    found: set[str] = set()
    if operation_kind != "artifact-remediation":
        raise ValueError(f"invalid remediation operation kind: {operation_kind}")
    replacement_status = "fixed"
    replacement_decision = "fix"
    output: list[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("|") and not stripped.startswith("|---"):
            cells = [cell.strip() for cell in stripped.split("|")[1:-1]]
            lowered = [cell.lower() for cell in cells]
            if "id" in lowered and "status" in lowered and "decision" in lowered:
                header = lowered
            elif header is not None and len(cells) == len(header):
                issue_id = cells[header.index("id")]
                if issue_id in selected:
                    cells[header.index("status")] = replacement_status
                    cells[header.index("decision")] = replacement_decision
                    ending = "\n" if raw_line.endswith("\n") else ""
                    raw_line = "| " + " | ".join(cells) + " |" + ending
                    found.add(issue_id)
        output.append(raw_line)
    if found != selected:
        missing = sorted(selected - found)
        raise ValueError(f"review issue ids could not be updated: {missing!r}")
    rendered = "".join(output)
    errors = validate_review_content(rendered, phase="remediation")
    if errors:
        raise ValueError(f"generated remediation review invalid: {'; '.join(errors)}")
    return rendered


def _human_resolution_rows(
    rows: list[dict[str, str]],
    *,
    issue_ids: list[str],
    resolution_kind: str,
) -> str | None:
    """Authorize selected pending Human Resolution rows."""
    by_id = {row.get("id", ""): row for row in rows}
    if len(by_id) != len(rows):
        return "review contains duplicate issue ids"
    for issue_id in issue_ids:
        row = by_id.get(issue_id)
        if row is None:
            return f"issue id is not in this dimension review: {issue_id}"
        if row.get("status", "").lower() != "pending":
            return f"issue id is not pending: {issue_id}"
        root_cause = row.get("root_cause", "").upper()
        if root_cause not in {"SOT-DEFECT", "UNRESOLVABLE", "DECISION-REQUIRED"}:
            return f"issue id is not a pending Human Resolution row: {issue_id}"
        if (
            resolution_kind in {"select", "allow-multiple"}
            and root_cause != "DECISION-REQUIRED"
        ):
            return (
                f"{resolution_kind} is only authorized for pending "
                f"DECISION-REQUIRED rows: {issue_id}"
            )
    return None


def _render_human_resolved_review(
    content: str,
    *,
    issue_ids: list[str],
    resolution_kind: str,
    resolution: str,
) -> str:
    """Persist a human disposition without modifying EvalTarget B."""
    lines = content.splitlines(keepends=True)
    header: list[str] | None = None
    selected = set(issue_ids)
    found: set[str] = set()
    output: list[str] = []
    for raw_line in lines:
        stripped = raw_line.strip()
        if stripped.startswith("|") and not stripped.startswith("|---"):
            cells = [cell.strip() for cell in stripped.split("|")[1:-1]]
            lowered = [cell.lower() for cell in cells]
            if "id" in lowered and "status" in lowered and "decision" in lowered:
                header = lowered
            elif header is not None and len(cells) == len(header):
                issue_id = cells[header.index("id")]
                if issue_id in selected:
                    if resolution_kind == "escalate":
                        cells[header.index("status")] = "escalated"
                        cells[header.index("decision")] = "escalate"
                    else:
                        cells[header.index("root_cause")] = "WO-ERROR"
                        cells[header.index("status")] = "pending"
                        cells[header.index("decision")] = "—"
                    cells[header.index("resolution")] = resolution
                    ending = "\n" if raw_line.endswith("\n") else ""
                    raw_line = "| " + " | ".join(cells) + " |" + ending
                    found.add(issue_id)
        output.append(raw_line)
    if found != selected:
        missing = sorted(selected - found)
        raise ValueError(f"review issue ids could not be updated: {missing!r}")
    rendered = "".join(output)
    errors = validate_review_content(rendered, phase="remediation")
    if errors:
        raise ValueError(
            f"generated human resolution review invalid: {'; '.join(errors)}",
        )
    return rendered


def _render_probe_review(
    *,
    dimension_label: str,
    active_doc: int,
    evaluate_round: int,
    method_focus: str,
    findings: list[dict[str, Any]],
) -> str:
    """Render a validated ReviewFile without exposing its path to the runner."""
    template_path = _EVAL_LIB.parent / "review.template.md"
    template = template_path.read_text(encoding="utf-8")
    if "| resolution |" not in template.lower():
        template = template.replace(
            "| description | status | decision |\n",
            "| description | status | decision | resolution |\n",
        ).replace(
            "|-------------|--------|----------|\n",
            "|-------------|--------|----------|------------|\n",
        )
    content = (
        template.replace("{{DIM_LABEL}}", dimension_label)
        .replace("{{REV}}", str(active_doc))
        .replace("{{M}}", str(evaluate_round))
        .replace("{{DATE}}", date.today().isoformat())
        .replace("{{REFS}}", method_focus)
    )
    for finding in findings:
        row = {
            **finding,
            "sot_ref": finding.get("sot_ref", "—"),
            "status": "pending",
            "decision": "—",
            "resolution": "",
        }
        content += (
            f"| {row['id']} | {row['root_cause']} | {row['sot_ref']} | "
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
        payload, submission_digest = _load_probe_payload(payload_file)
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
    lock_path = operations_path.with_suffix(operations_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)

    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            try:
                _refresh_handoff(cycle_id, project_root, require_evaluating=True)
                paths = _eval_paths(
                    cycle_id,
                    project_root,
                    active_doc=active_doc,
                    evaluate_round=evaluate_round,
                    es_path=_evaluate_state_path(cycle_id, project_root),
                )
            except ValueError as exc:
                return _failure(_CMD_SUBMIT_PROBE_FINDINGS, str(exc))
            try:
                record = get_operation_record(operations_path, dimension_token)
            except ValueError as exc:
                return _failure(_CMD_SUBMIT_PROBE_FINDINGS, str(exc))
            if record.get("status") == "closed":
                if record.get("submission_digest") == submission_digest:
                    return _success(
                        _CMD_SUBMIT_PROBE_FINDINGS,
                        dimension_token=dimension_token,
                        outcome="probed",
                        idempotent=True,
                        review_path=record["review_path"],
                    )
                return _failure(
                    _CMD_SUBMIT_PROBE_FINDINGS,
                    "conflicting submission for closed dimension_token",
                    dimension_token=dimension_token,
                )
            if (
                record.get("operation_kind") != "probe"
                or record.get("allowed_submission") != "finding"
                or record.get("round_token") != eval_data["round_token"]
            ):
                return _failure(
                    _CMD_SUBMIT_PROBE_FINDINGS,
                    "dimension_token is not authorized for this probe round",
                    dimension_token=dimension_token,
                )

            dimension_id = str(record["dimension_id"])
            dimension_tokens = parse_dimension_tokens(eval_data["dimension_tokens"])
            dimension_status = parse_dimension_status(eval_data["dimension_status"])
            if (
                dimension_tokens.get(dimension_id) != dimension_token
                or dimension_status.get(dimension_id) != "in_progress"
            ):
                return _failure(
                    _CMD_SUBMIT_PROBE_FINDINGS,
                    "dimension_token does not own an in-progress dimension",
                    dimension_token=dimension_token,
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
                    active_doc=active_doc,
                    evaluate_round=evaluate_round,
                    method_focus=str(dim_def["method"].get("focus", "")),
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
            publish_error = _publish_probe_review(
                cycle_id,
                project_root,
                paths=paths,
                evaluate_round=evaluate_round,
                formal_review_path=review_path,
                content=review_content,
            )
            if publish_error is not None:
                return _failure(
                    _CMD_SUBMIT_PROBE_FINDINGS,
                    publish_error,
                    dimension_token=dimension_token,
                )

            corpus = _load_corpus(cycle_id, project_root)
            total_issues = str(len(payload["findings"]))

            def _patch(data: dict[str, str]) -> dict[str, str]:
                updated = merge_current_dimension(
                    data,
                    dimension_id,
                    "probed",
                    corpus=corpus,
                )
                return patch_issue_count(updated, dimension_id, total=total_issues)

            error = _commit_staged_evaluate_state(
                cycle_id,
                project_root,
                update=_patch,
            )
            if error is not None:
                if not str(paths.get("lease_id", "")).strip():
                    review_path.unlink(missing_ok=True)
                return _failure(
                    _CMD_SUBMIT_PROBE_FINDINGS,
                    error,
                    dimension_token=dimension_token,
                )
            review_digest = hashlib.sha256(review_content.encode("utf-8")).hexdigest()
            try:
                close_probe_operation(
                    operations_path,
                    dimension_token=dimension_token,
                    submission_digest=submission_digest,
                    review_path=review_path,
                    review_digest=review_digest,
                    findings=payload["findings"],
                )
            except ValueError as exc:
                return _failure(_CMD_SUBMIT_PROBE_FINDINGS, str(exc))
            return _success(
                _CMD_SUBMIT_PROBE_FINDINGS,
                dimension_token=dimension_token,
                outcome="probed",
                idempotent=False,
                total_issues=total_issues,
                review_path=review_path.resolve().as_posix(),
            )
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def submit_remediation_diff(
    cycle_id: str,
    project_root: Path,
    *,
    payload_file: Path,
) -> dict[str, Any]:
    """Validate and transactionally publish one token-scoped remediation diff."""
    try:
        payload, submission_digest = _load_remediation_payload(payload_file)
    except ValueError as exc:
        return _failure(_CMD_SUBMIT_REMEDIATION_DIFF, str(exc))

    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_SUBMIT_REMEDIATION_DIFF
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
    lock_path = operations_path.with_suffix(operations_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)

    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            try:
                _refresh_handoff(cycle_id, project_root, require_evaluating=True)
                paths = _eval_paths(
                    cycle_id,
                    project_root,
                    active_doc=active_doc,
                    evaluate_round=evaluate_round,
                    es_path=_evaluate_state_path(cycle_id, project_root),
                )
                record = get_operation_record(operations_path, dimension_token)
            except ValueError as exc:
                return _failure(_CMD_SUBMIT_REMEDIATION_DIFF, str(exc))
            if record.get("status") == "closed":
                if record.get("submission_digest") == submission_digest:
                    return _success(
                        _CMD_SUBMIT_REMEDIATION_DIFF,
                        dimension_token=dimension_token,
                        outcome="remediated",
                        idempotent=True,
                    )
                return _failure(
                    _CMD_SUBMIT_REMEDIATION_DIFF,
                    "conflicting submission for closed dimension_token",
                    dimension_token=dimension_token,
                )
            operation_kind = str(record.get("operation_kind", ""))
            if (
                operation_kind != "artifact-remediation"
                or record.get("allowed_submission") != "unified_diff"
                or record.get("round_token") != eval_data["round_token"]
            ):
                return _failure(
                    _CMD_SUBMIT_REMEDIATION_DIFF,
                    "dimension_token is not authorized for remediation",
                    dimension_token=dimension_token,
                )
            try:
                snapshot = read_target_snapshot(
                    operations_path=operations_path,
                    dimension_token=dimension_token,
                )
            except ValueError as exc:
                return _failure(_CMD_SUBMIT_REMEDIATION_DIFF, str(exc))
            if payload["base_digest"] != snapshot["digest"]:
                return _failure(
                    _CMD_SUBMIT_REMEDIATION_DIFF,
                    "base_digest does not match the token B snapshot",
                    dimension_token=dimension_token,
                )
            try:
                remediated_target = apply_unified_diff(
                    snapshot["content"],
                    str(payload["unified_diff"]),
                )
            except ValueError as exc:
                return _failure(_CMD_SUBMIT_REMEDIATION_DIFF, str(exc))

            dimension_id = str(record["dimension_id"])
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
                    _CMD_SUBMIT_REMEDIATION_DIFF,
                    f"review file not found: {review_path}",
                    dimension_token=dimension_token,
                )
            review_before = review_path.read_text(encoding="utf-8")
            issue_ids = list(payload["issue_ids"])
            row_error = _remediation_rows(
                parse_review_file(review_path),
                issue_ids=issue_ids,
                operation_kind=operation_kind,
            )
            if row_error:
                return _failure(
                    _CMD_SUBMIT_REMEDIATION_DIFF,
                    row_error,
                    dimension_token=dimension_token,
                )
            try:
                review_after = _render_remediated_review(
                    review_before,
                    issue_ids=issue_ids,
                    operation_kind=operation_kind,
                )
            except ValueError as exc:
                return _failure(_CMD_SUBMIT_REMEDIATION_DIFF, str(exc))

            scope_dir = Path(str(record["snapshot_path"])).parent
            staged_target = scope_dir / "target.remediated"
            _atomic_write_text(staged_target, remediated_target)
            target_digest = hashlib.sha256(
                remediated_target.encode("utf-8"),
            ).hexdigest()
            target_commit = _adapter().commit_remediation_target(
                cycle_id,
                project_root,
                staged_target_path=staged_target,
                base_digest=str(payload["base_digest"]),
                lease_id=str(record["lease_id"]),
            )
            if not target_commit.get("ok"):
                return _failure(
                    _CMD_SUBMIT_REMEDIATION_DIFF,
                    str(target_commit.get("error") or "commit-remediation-target failed"),
                    dimension_token=dimension_token,
                )

            def _rollback_target() -> None:
                _adapter().restore_remediation_target(
                    cycle_id,
                    project_root,
                    snapshot_path=Path(str(record["snapshot_path"])),
                    expected_digest=target_digest,
                    lease_id=str(record["lease_id"]),
                )

            try:
                _atomic_write_text(review_path, review_after)
            except OSError as exc:
                _rollback_target()
                return _failure(_CMD_SUBMIT_REMEDIATION_DIFF, f"review publish failed: {exc}")

            resolved = count_resolved(parse_review_file(review_path))

            def _patch(data: dict[str, str]) -> dict[str, str]:
                return patch_issue_count(
                    data,
                    dimension_id,
                    resolved=str(resolved),
                )

            state_error = _commit_staged_evaluate_state(
                cycle_id,
                project_root,
                update=_patch,
            )
            if state_error is not None:
                _atomic_write_text(review_path, review_before)
                _rollback_target()
                return _failure(
                    _CMD_SUBMIT_REMEDIATION_DIFF,
                    state_error,
                    dimension_token=dimension_token,
                )
            try:
                close_operation(
                    operations_path,
                    dimension_token=dimension_token,
                    submission_digest=submission_digest,
                    review_path=review_path,
                    review_digest=hashlib.sha256(
                        review_after.encode("utf-8"),
                    ).hexdigest(),
                )
            except ValueError as exc:
                _commit_staged_evaluate_state(
                    cycle_id,
                    project_root,
                    state=eval_data,
                )
                _atomic_write_text(review_path, review_before)
                _rollback_target()
                return _failure(_CMD_SUBMIT_REMEDIATION_DIFF, str(exc))
            return _success(
                _CMD_SUBMIT_REMEDIATION_DIFF,
                dimension_token=dimension_token,
                outcome="remediated",
                idempotent=False,
                issue_ids=issue_ids,
            )
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def submit_human_resolution(
    cycle_id: str,
    project_root: Path,
    *,
    payload_file: Path,
) -> dict[str, Any]:
    """Validate and atomically publish one Human Resolution disposition."""
    try:
        payload, submission_digest = _load_human_resolution_payload(payload_file)
    except ValueError as exc:
        return _failure(_CMD_SUBMIT_HUMAN_RESOLUTION, str(exc))

    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_SUBMIT_HUMAN_RESOLUTION
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
    lock_path = operations_path.with_suffix(operations_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.touch(exist_ok=True)

    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            try:
                _refresh_handoff(cycle_id, project_root, require_evaluating=True)
                record = get_operation_record(operations_path, dimension_token)
            except ValueError as exc:
                return _failure(_CMD_SUBMIT_HUMAN_RESOLUTION, str(exc))
            if record.get("status") == "closed":
                if record.get("submission_digest") == submission_digest:
                    return _success(
                        _CMD_SUBMIT_HUMAN_RESOLUTION,
                        dimension_token=dimension_token,
                        outcome="resolved",
                        idempotent=True,
                    )
                return _failure(
                    _CMD_SUBMIT_HUMAN_RESOLUTION,
                    "conflicting submission for closed dimension_token",
                    dimension_token=dimension_token,
                )
            if (
                record.get("operation_kind") != "human-resolution"
                or record.get("allowed_submission") != "resolution"
                or record.get("round_token") != eval_data["round_token"]
            ):
                return _failure(
                    _CMD_SUBMIT_HUMAN_RESOLUTION,
                    "dimension_token is not authorized for Human Resolution",
                    dimension_token=dimension_token,
                )
            dimension_id = str(record["dimension_id"])
            dimension_tokens = parse_dimension_tokens(eval_data["dimension_tokens"])
            if dimension_tokens.get(dimension_id) != dimension_token:
                return _failure(
                    _CMD_SUBMIT_HUMAN_RESOLUTION,
                    "dimension_token does not own this Human Resolution dimension",
                    dimension_token=dimension_token,
                )
            try:
                snapshot = read_target_snapshot(
                    operations_path=operations_path,
                    dimension_token=dimension_token,
                )
            except ValueError as exc:
                return _failure(_CMD_SUBMIT_HUMAN_RESOLUTION, str(exc))
            if payload["base_digest"] != snapshot["digest"]:
                return _failure(
                    _CMD_SUBMIT_HUMAN_RESOLUTION,
                    "base_digest does not match the token B snapshot",
                    dimension_token=dimension_token,
                )

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
                    _CMD_SUBMIT_HUMAN_RESOLUTION,
                    f"review file not found: {review_path}",
                    dimension_token=dimension_token,
                )
            review_before = review_path.read_text(encoding="utf-8")
            issue_ids = list(payload["issue_ids"])
            resolution_kind = str(payload["resolution_kind"])
            row_error = _human_resolution_rows(
                parse_review_file(review_path),
                issue_ids=issue_ids,
                resolution_kind=resolution_kind,
            )
            if row_error:
                return _failure(
                    _CMD_SUBMIT_HUMAN_RESOLUTION,
                    row_error,
                    dimension_token=dimension_token,
                )
            try:
                review_after = _render_human_resolved_review(
                    review_before,
                    issue_ids=issue_ids,
                    resolution_kind=resolution_kind,
                    resolution=str(payload["resolution"]),
                )
            except ValueError as exc:
                return _failure(_CMD_SUBMIT_HUMAN_RESOLUTION, str(exc))

            try:
                _atomic_write_text(review_path, review_after)
            except OSError as exc:
                return _failure(
                    _CMD_SUBMIT_HUMAN_RESOLUTION,
                    f"review publish failed: {exc}",
                )
            resolved = count_resolved(parse_review_file(review_path))
            state_error = _commit_staged_evaluate_state(
                cycle_id,
                project_root,
                update=lambda data: patch_issue_count(
                    data,
                    dimension_id,
                    resolved=str(resolved),
                ),
            )
            if state_error is not None:
                _atomic_write_text(review_path, review_before)
                return _failure(
                    _CMD_SUBMIT_HUMAN_RESOLUTION,
                    state_error,
                    dimension_token=dimension_token,
                )
            try:
                close_operation(
                    operations_path,
                    dimension_token=dimension_token,
                    submission_digest=submission_digest,
                    review_path=review_path,
                    review_digest=hashlib.sha256(
                        review_after.encode("utf-8"),
                    ).hexdigest(),
                    resolution_records=[{
                        "issue_ids": issue_ids,
                        "resolution_kind": resolution_kind,
                        "resolution": str(payload["resolution"]),
                    }],
                )
            except ValueError as exc:
                _commit_staged_evaluate_state(
                    cycle_id,
                    project_root,
                    state=eval_data,
                )
                _atomic_write_text(review_path, review_before)
                return _failure(_CMD_SUBMIT_HUMAN_RESOLUTION, str(exc))
            return _success(
                _CMD_SUBMIT_HUMAN_RESOLUTION,
                dimension_token=dimension_token,
                outcome="resolved",
                idempotent=False,
                issue_ids=issue_ids,
                resolution_kind=resolution_kind,
            )
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


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

    if review_path.exists() and dim_status != "probed":
        return _failure(
            _CMD_CHECK_DIMENSION,
            (
                f"review exists but {dim} status is {dim_status!r}, "
                "expected 'probed' (submit-probe-findings did not complete?)."
            ),
            current_state=state["current_state"],
            dim=dim,
            outcome="incomplete",
            abandoned=False,
            dim_status=dim_status,
            review_path=review_path.resolve().as_posix(),
        )

    if dim_status != "probed":
        return _failure(
            _CMD_CHECK_DIMENSION,
            f"{dim} status is {dim_status!r}, expected 'probed'.",
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

    dimension_tokens = parse_dimension_tokens(eval_data["dimension_tokens"])
    for dimension_id in _dispatch_canonical(cycle_id, project_root):
        token = dimension_tokens.get(dimension_id)
        if not token:
            continue
        try:
            record = get_operation_record(_operations_path(paths), token)
        except ValueError:
            continue
        findings = record.get("probe_findings")
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


def probe_complete(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Return probe findings and advance to Human Resolution."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_PROBE_COMPLETE
        return ctx

    state, _ws_path, eval_data, _evaluate_round, active_doc, _mode = ctx
    dispatch = _dispatch_canonical(cycle_id, project_root)

    if eval_data.get("fix_phase") != "probe":
        return _failure(
            _CMD_PROBE_COMPLETE,
            f"fix_phase is {eval_data.get('fix_phase')!r}, expected 'probe'.",
            current_state=state["current_state"],
        )

    if not all_dims_at_least(eval_data, dispatch, "probed"):
        return _failure(
            _CMD_PROBE_COMPLETE,
            "not all dispatch dimensions are probed.",
            current_state=state["current_state"],
        )

    total = sum_issue_totals(eval_data, dispatch)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=_evaluate_round,
        es_path=_evaluate_state_path(cycle_id, project_root),
    )
    issues, review_paths = _probe_result_issues(
        cycle_id=cycle_id,
        project_root=project_root,
        eval_data=eval_data,
        paths=paths,
    )

    error = _commit_staged_evaluate_state(
        cycle_id,
        project_root,
        patch={
            "total_issues": str(total),
            "fix_phase": "human-resolution",
        },
    )
    if error is not None:
        return _failure(_CMD_PROBE_COMPLETE, error, current_state=state["current_state"])

    return _success(
        _CMD_PROBE_COMPLETE,
        fix_phase="human-resolution",
        total_issues=str(total),
        current_state=state["current_state"],
        issues=issues,
        review_paths=review_paths,
    )


def _build_remediation_operation_context(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
    state: dict[str, str],
    paths: dict[str, str],
    evaluate_round: int,
    round_token: str,
    operation_kind: str,
) -> dict[str, Any]:
    expanded = _expanded_corpus(
        cycle_id,
        state,
        paths,
        evaluate_round,
        project_root=project_root,
    )
    dim_def = _dimension_def(expanded, dim)
    return issue_remediation_context(
        operations_path=_operations_path(paths),
        write_staging_dir=Path(
            paths.get("write_staging_dir") or paths["evaluate_dir"],
        ),
        target_path=Path(str(dim_def["eval_target"]["path"])),
        round_token=round_token,
        dimension_id=str(dim_def["id"]),
        operation_kind=operation_kind,
        lease_id=str(paths.get("lease_id", "")),
        method=dict(dim_def["method"]),
        sots=[dict(sot) for sot in dim_def["sots"]],
    )


def _format_remediation_dispatch_input(
    operation_ctx: dict[str, Any],
    pending_issues: list[dict[str, str]],
) -> str:
    lines = [
        f"ROUND_TOKEN: {operation_ctx['round_token']}",
        f"DIMENSION_TOKEN: {operation_ctx['dimension_token']}",
        f"DIMENSION_ID: {operation_ctx['dimension_id']}",
        f"OPERATION_KIND: {operation_ctx['operation_kind']}",
        f"BASE_DIGEST: {operation_ctx['target_digest']}",
        f"ALLOWED_SUBMISSION: {operation_ctx['allowed_submission']}",
        "RESOLVED_METHOD: "
        + json.dumps(operation_ctx["resolved_method"], ensure_ascii=False),
        "RESOLVED_SOTS: "
        + json.dumps(operation_ctx["resolved_sots"], ensure_ascii=False),
        "PENDING_ISSUES: " + json.dumps(pending_issues, ensure_ascii=False),
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


def _dims_with_pending_artifact(
    cycle_id: str,
    project_root: Path,
    *,
    state: dict[str, str],
    evaluate_round: int,
    active_doc: int,
) -> list[str]:
    pending_dims: list[str] = []
    for dim in dispatch_list(cycle_id, project_root):
        rows = _review_rows_for_dim(
            cycle_id,
            project_root,
            state=state,
            evaluate_round=evaluate_round,
            active_doc=active_doc,
            dim=dim,
        )
        if pending_artifact_rows(rows):
            pending_dims.append(dim)
    return pending_dims


def _dims_with_pending_human(
    cycle_id: str,
    project_root: Path,
    *,
    state: dict[str, str],
    evaluate_round: int,
    active_doc: int,
) -> list[str]:
    pending_dims: list[str] = []
    for dim in dispatch_list(cycle_id, project_root):
        rows = _review_rows_for_dim(
            cycle_id,
            project_root,
            state=state,
            evaluate_round=evaluate_round,
            active_doc=active_doc,
            dim=dim,
        )
        if pending_human_rows(rows):
            pending_dims.append(dim)
    return pending_dims


def begin_artifact_remediation(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Return artifact remediation dispatch list or skip when no pending WO-* rows."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_BEGIN_ARTIFACT_REMEDIATION
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if eval_data.get("fix_phase") != "artifact-remediation":
        return _failure(
            _CMD_BEGIN_ARTIFACT_REMEDIATION,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'artifact-remediation'."
            ),
            current_state=state["current_state"],
        )
    pending_human_dims = _dims_with_pending_human(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
    )
    if pending_human_dims:
        return _failure(
            _CMD_BEGIN_ARTIFACT_REMEDIATION,
            (
                "pending Human Resolution rows remain for dimensions: "
                f"{pending_human_dims!r}."
            ),
            current_state=state["current_state"],
        )

    pending_dims = _dims_with_pending_artifact(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
    )
    if not pending_dims:
        return _success(
            _CMD_BEGIN_ARTIFACT_REMEDIATION,
            skip=True,
            dispatch=[],
            dimension_dispatch=eval_data.get("dimension_dispatch", "parallel"),
            current_state=state["current_state"],
        )

    return _success(
        _CMD_BEGIN_ARTIFACT_REMEDIATION,
        skip=False,
        dispatch=pending_dims,
        dimension_dispatch=eval_data.get("dimension_dispatch", "parallel"),
        current_state=state["current_state"],
        pending_count=len(pending_dims),
    )


def begin_dimension_artifact_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Return per-dimension artifact remediation dispatch input (plain text)."""
    if not dim.strip():
        return _failure(_CMD_BEGIN_DIMENSION_ARTIFACT, "invalid dim: empty string")

    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_BEGIN_DIMENSION_ARTIFACT
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if not _dispatch_dim_allowed(cycle_id, project_root, dim):
        return _failure(
            _CMD_BEGIN_DIMENSION_ARTIFACT,
            f"invalid dim: {dim!r} (not in corpus for mode {mode!r}).",
        )
    if eval_data.get("fix_phase") != "artifact-remediation":
        return _failure(
            _CMD_BEGIN_DIMENSION_ARTIFACT,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'artifact-remediation'."
            ),
            current_state=state["current_state"],
        )
    if _dims_with_pending_human(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
    ):
        return _failure(
            _CMD_BEGIN_DIMENSION_ARTIFACT,
            "pending Human Resolution rows must be resolved before Artifact Remediation.",
            dim=dim,
        )

    rows = _review_rows_for_dim(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
        dim=dim,
    )
    if not pending_artifact_rows(rows):
        return _failure(
            _CMD_BEGIN_DIMENSION_ARTIFACT,
            f"no pending WO-* rows for dim {dim!r}.",
            dim=dim,
        )

    try:
        _refresh_handoff(cycle_id, project_root, require_evaluating=True)
    except ValueError as exc:
        return _failure(_CMD_BEGIN_DIMENSION_ARTIFACT, str(exc), dim=dim)
    es_path = _evaluate_state_path(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    try:
        operation_ctx = _build_remediation_operation_context(
            cycle_id,
            project_root,
            dim=dim,
            state=state,
            paths=paths,
            evaluate_round=evaluate_round,
            round_token=eval_data["round_token"],
            operation_kind="artifact-remediation",
        )
    except (OSError, ValueError) as exc:
        return _failure(_CMD_BEGIN_DIMENSION_ARTIFACT, str(exc), dim=dim)
    return _success(
        _CMD_BEGIN_DIMENSION_ARTIFACT,
        dim=dim,
        current_state=state["current_state"],
        operation_ctx=operation_ctx,
        dispatch_input=_format_remediation_dispatch_input(
            operation_ctx,
            pending_artifact_rows(rows),
        ),
    )


def check_dimension_artifact_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Reconcile WO-* rows for one dimension after artifact runner."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_CHECK_DIMENSION_ARTIFACT
        ctx["dim"] = dim
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if not _dispatch_dim_allowed(cycle_id, project_root, dim):
        return _failure(
            _CMD_CHECK_DIMENSION_ARTIFACT,
            f"invalid dim: {dim!r} (not in corpus for mode {mode!r}).",
            dim=dim,
        )

    review_path = _review_path_from_context(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
        dim=dim,
    )
    errors = validate_review_file(review_path, phase="remediation")
    if errors:
        return _failure(
            _CMD_CHECK_DIMENSION_ARTIFACT,
            "; ".join(errors),
            dim=dim,
            review_path=review_path.as_posix(),
        )

    rows = parse_review_file(review_path)
    if pending_artifact_rows(rows):
        return _failure(
            _CMD_CHECK_DIMENSION_ARTIFACT,
            f"pending WO-* rows remain for dim {dim!r}.",
            dim=dim,
        )

    dim_id = _canonical_dim(cycle_id, project_root, dim)
    merged = patch_issue_count(
        eval_data,
        dim_id,
        resolved=str(count_resolved(rows)),
    )
    corpus = _load_corpus(cycle_id, project_root)
    if not pending_human_rows(rows):
        merged = merge_current_dimension(merged, dim, "complete", corpus=corpus)

    error = _commit_staged_evaluate_state(
        cycle_id,
        project_root,
        patch={
            "issue_counts": merged["issue_counts"],
            "dimension_status": merged["dimension_status"],
        },
    )
    if error is not None:
        return _failure(_CMD_CHECK_DIMENSION_ARTIFACT, error, dim=dim)

    return _success(
        _CMD_CHECK_DIMENSION_ARTIFACT,
        dim=dim,
        resolved=count_resolved(rows),
        current_state=state["current_state"],
    )


def artifact_remediation_complete(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Finalize Artifact Remediation after every pending artifact row is fixed."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_ARTIFACT_REMEDIATION_COMPLETE
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if eval_data.get("fix_phase") != "artifact-remediation":
        return _failure(
            _CMD_ARTIFACT_REMEDIATION_COMPLETE,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'artifact-remediation'."
            ),
            current_state=state["current_state"],
        )

    dispatch = dispatch_list(cycle_id, project_root)
    for dim in dispatch:
        rows = _review_rows_for_dim(
            cycle_id,
            project_root,
            state=state,
            evaluate_round=evaluate_round,
            active_doc=active_doc,
            dim=dim,
        )
        if pending_human_rows(rows):
            return _failure(
                _CMD_ARTIFACT_REMEDIATION_COMPLETE,
                f"pending Human Resolution rows remain for dim {dim!r}.",
                current_state=state["current_state"],
            )
        if pending_artifact_rows(rows):
            return _failure(
                _CMD_ARTIFACT_REMEDIATION_COMPLETE,
                f"pending WO-* rows remain for dim {dim!r}.",
                current_state=state["current_state"],
            )

    resolved_total = int(eval_data.get("resolved_issues", "0") or "0")
    counts = parse_issue_counts(eval_data.get("issue_counts", "{}"))
    if resolved_total == 0 and counts:
        resolved_total = sum(
            int(entry.get("resolved", "0") or "0") for entry in counts.values()
        )

    corpus = _load_corpus(cycle_id, project_root)

    def _complete_artifact_phase(data: dict[str, str]) -> dict[str, str]:
        updated = dict(data)
        for dim in dispatch:
            updated = merge_current_dimension(
                updated,
                dim,
                "complete",
                corpus=corpus,
            )
        updated["resolved_issues"] = str(resolved_total)
        updated["fix_phase"] = "done"
        return updated

    error = _commit_staged_evaluate_state(
        cycle_id,
        project_root,
        update=_complete_artifact_phase,
    )
    if error is not None:
        return _failure(
            _CMD_ARTIFACT_REMEDIATION_COMPLETE,
            error,
            current_state=state["current_state"],
        )

    return _success(
        _CMD_ARTIFACT_REMEDIATION_COMPLETE,
        fix_phase="done",
        current_state=state["current_state"],
        resolved_issues=str(resolved_total),
    )


def begin_human_resolution(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Return Human Resolution dispatch list or skip when no human rows remain."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_BEGIN_HUMAN_RESOLUTION
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if eval_data.get("fix_phase") != "human-resolution":
        return _failure(
            _CMD_BEGIN_HUMAN_RESOLUTION,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'human-resolution'."
            ),
            current_state=state["current_state"],
        )

    pending_dims = _dims_with_pending_human(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
    )
    if not pending_dims:
        return _success(
            _CMD_BEGIN_HUMAN_RESOLUTION,
            skip=True,
            dispatch=[],
            dimension_dispatch=eval_data.get("dimension_dispatch", "parallel"),
            current_state=state["current_state"],
        )

    return _success(
        _CMD_BEGIN_HUMAN_RESOLUTION,
        skip=False,
        dispatch=pending_dims,
        dimension_dispatch=eval_data.get("dimension_dispatch", "parallel"),
        current_state=state["current_state"],
        pending_count=len(pending_dims),
    )


def begin_dimension_human_resolution(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Return per-dimension Human Resolution dispatch input."""
    if not dim.strip():
        return _failure(_CMD_BEGIN_DIMENSION_HUMAN, "invalid dim: empty string")

    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_BEGIN_DIMENSION_HUMAN
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if not _dispatch_dim_allowed(cycle_id, project_root, dim):
        return _failure(
            _CMD_BEGIN_DIMENSION_HUMAN,
            f"invalid dim: {dim!r} (not in corpus for mode {mode!r}).",
        )
    if eval_data.get("fix_phase") != "human-resolution":
        return _failure(
            _CMD_BEGIN_DIMENSION_HUMAN,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'human-resolution'."
            ),
            current_state=state["current_state"],
        )

    rows = _review_rows_for_dim(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
        dim=dim,
    )
    if not pending_human_rows(rows):
        return _failure(
            _CMD_BEGIN_DIMENSION_HUMAN,
            f"no pending Human Resolution rows for dim {dim!r}.",
            dim=dim,
        )
    canonical_dim = _canonical_dim(cycle_id, project_root, dim)

    try:
        _refresh_handoff(cycle_id, project_root, require_evaluating=True)
    except ValueError as exc:
        return _failure(_CMD_BEGIN_DIMENSION_HUMAN, str(exc), dim=dim)
    es_path = _evaluate_state_path(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    try:
        operation_ctx = _build_remediation_operation_context(
            cycle_id,
            project_root,
            dim=dim,
            state=state,
            paths=paths,
            evaluate_round=evaluate_round,
            round_token=eval_data["round_token"],
            operation_kind="human-resolution",
        )
    except (OSError, ValueError) as exc:
        return _failure(_CMD_BEGIN_DIMENSION_HUMAN, str(exc), dim=dim)
    def _patch_human_token(data: dict[str, str]) -> dict[str, str]:
        updated = dict(data)
        dimension_tokens = parse_dimension_tokens(updated["dimension_tokens"])
        dimension_tokens[canonical_dim] = operation_ctx["dimension_token"]
        updated["dimension_tokens"] = json.dumps(
            dimension_tokens,
            separators=(",", ":"),
        )
        return updated

    error = _commit_staged_evaluate_state(
        cycle_id,
        project_root,
        update=_patch_human_token,
    )
    if error is not None:
        try:
            discard_operation_context(
                operations_path=_operations_path(paths),
                dimension_token=operation_ctx["dimension_token"],
            )
        except (OSError, ValueError):
            pass
        return _failure(_CMD_BEGIN_DIMENSION_HUMAN, error, dim=dim)
    return _success(
        _CMD_BEGIN_DIMENSION_HUMAN,
        dim=dim,
        current_state=state["current_state"],
        operation_ctx=operation_ctx,
        dispatch_input=_format_remediation_dispatch_input(
            operation_ctx,
            pending_human_rows(rows),
        ),
    )


def check_dimension_human_resolution(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Reconcile Human Resolution rows for one dimension."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_CHECK_DIMENSION_HUMAN
        ctx["dim"] = dim
        ctx["abandoned"] = False
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if not _dispatch_dim_allowed(cycle_id, project_root, dim):
        return _failure(
            _CMD_CHECK_DIMENSION_HUMAN,
            f"invalid dim: {dim!r} (not in corpus for mode {mode!r}).",
            dim=dim,
            abandoned=False,
        )

    review_path = _review_path_from_context(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
        dim=dim,
    )
    errors = validate_review_file(review_path, phase="remediation")
    if errors:
        return _failure(
            _CMD_CHECK_DIMENSION_HUMAN,
            "; ".join(errors),
            dim=dim,
            abandoned=False,
        )

    rows = parse_review_file(review_path)
    if pending_human_rows(rows):
        return _failure(
            _CMD_CHECK_DIMENSION_HUMAN,
            f"pending Human Resolution rows remain for dim {dim!r}.",
            dim=dim,
            abandoned=False,
        )

    escalated = has_escalated(rows)
    dim_id = _canonical_dim(cycle_id, project_root, dim)
    merged = patch_issue_count(
        eval_data,
        dim_id,
        resolved=str(count_resolved(rows)),
    )
    patch: dict[str, str] = {
        "issue_counts": merged["issue_counts"],
    }
    if escalated:
        patch["eval_status"] = "abandoned"

    error = _commit_staged_evaluate_state(
        cycle_id,
        project_root,
        patch=patch,
    )
    if error is not None:
        return _failure(
            _CMD_CHECK_DIMENSION_HUMAN,
            error,
            dim=dim,
            abandoned=False,
        )

    return _success(
        _CMD_CHECK_DIMENSION_HUMAN,
        dim=dim,
        abandoned=escalated,
        current_state=state["current_state"],
    )


def human_resolution_complete(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Finalize Human Resolution; continue to Artifact Remediation when clear."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_HUMAN_RESOLUTION_COMPLETE
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    dispatch = dispatch_list(cycle_id, project_root)

    if eval_data.get("fix_phase") != "human-resolution":
        return _failure(
            _CMD_HUMAN_RESOLUTION_COMPLETE,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'human-resolution'."
            ),
            current_state=state["current_state"],
        )

    if eval_data.get("eval_status") == "abandoned":
        error = _commit_staged_evaluate_state(
            cycle_id,
            project_root,
            patch={"fix_phase": "done"},
        )
        if error is not None:
            return _failure(
                _CMD_HUMAN_RESOLUTION_COMPLETE,
                error,
                current_state=state["current_state"],
            )
        return _success(
            _CMD_HUMAN_RESOLUTION_COMPLETE,
            fix_phase="done",
            abandoned=True,
            current_state=state["current_state"],
        )

    escalated = False
    for dim in dispatch:
        rows = _review_rows_for_dim(
            cycle_id,
            project_root,
            state=state,
            evaluate_round=evaluate_round,
            active_doc=active_doc,
            dim=dim,
        )
        if pending_human_rows(rows):
            return _failure(
                _CMD_HUMAN_RESOLUTION_COMPLETE,
                f"pending Human Resolution rows remain for dim {dim!r}.",
                current_state=state["current_state"],
            )
        escalated = escalated or has_escalated(rows)

    if escalated:
        error = _commit_staged_evaluate_state(
            cycle_id,
            project_root,
            patch={"eval_status": "abandoned", "fix_phase": "done"},
        )
        if error is not None:
            return _failure(
                _CMD_HUMAN_RESOLUTION_COMPLETE,
                error,
                current_state=state["current_state"],
            )
        return _success(
            _CMD_HUMAN_RESOLUTION_COMPLETE,
            fix_phase="done",
            abandoned=True,
            current_state=state["current_state"],
        )

    error = _commit_staged_evaluate_state(
        cycle_id,
        project_root,
        patch={
            "fix_phase": "artifact-remediation",
        },
    )
    if error is not None:
        return _failure(
            _CMD_HUMAN_RESOLUTION_COMPLETE,
            error,
            current_state=state["current_state"],
        )
    return _success(
        _CMD_HUMAN_RESOLUTION_COMPLETE,
        fix_phase="artifact-remediation",
        abandoned=False,
        current_state=state["current_state"],
    )


def complete_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Finalize evaluation round: compute severity, write done, return summary."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_COMPLETE_ROUND
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    dispatch = _dispatch_canonical(cycle_id, project_root)

    eval_status = eval_data.get("eval_status", "")
    if eval_status == "done":
        return _failure(
            _CMD_COMPLETE_ROUND,
            "evaluate round is already complete (eval_status: done).",
            current_state=state["current_state"],
        )
    if eval_status == "abandoned":
        return _failure(
            _CMD_COMPLETE_ROUND,
            "evaluation was abandoned (eval_status: abandoned).",
            current_state=state["current_state"],
        )
    if eval_data.get("fix_phase") != "done":
        return _failure(
            _CMD_COMPLETE_ROUND,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'done'."
            ),
            current_state=state["current_state"],
        )

    if not all_dims_at_least(eval_data, dispatch, "complete"):
        return _failure(
            _CMD_COMPLETE_ROUND,
            "not all dispatch dimensions are complete.",
            current_state=state["current_state"],
        )

    eval_dir = _eval_dir(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
    )
    corpus = _load_corpus(cycle_id, project_root)
    issues, review_paths = collect_review_issues(
        eval_dir,
        cycle_id=cycle_id,
        project_root=project_root,
    )
    fix_severity, fix_severity_reason = compute_fix_severity(issues)

    error = _commit_staged_evaluate_state(
        cycle_id,
        project_root,
        patch={
            "eval_status": "done",
            "fix_severity": fix_severity,
            "fix_severity_reason": fix_severity_reason,
        },
    )
    if error is not None:
        return _failure(_CMD_COMPLETE_ROUND, error, current_state=state["current_state"])
    es_path = _evaluate_state_path(cycle_id, project_root)
    eval_data = load_evaluate_state(es_path)

    return _success(
        _CMD_COMPLETE_ROUND,
        evaluate_round=evaluate_round,
        current_state=state["current_state"],
        eval_status="done",
        fix_severity=eval_data.get("fix_severity", ""),
        fix_severity_reason=eval_data.get("fix_severity_reason", ""),
        counts=build_issue_counts(eval_data, issues),
        dimensions=build_dimensions(eval_data, corpus=corpus),
        issues=issues,
        review_paths=review_paths,
    )



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
    snapshot_parser.add_argument("--dimension-token", required=True)

    evidence_snapshot_parser = sub.add_parser(
        _CMD_READ_EVIDENCE_SNAPSHOT,
        help="Read token-authorized dynamic SoT evidence",
    )
    evidence_snapshot_parser.add_argument("--dimension-token", required=True)
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
    submit_remediation_parser = sub.add_parser(
        _CMD_SUBMIT_REMEDIATION_DIFF,
        help="Validate and publish a token-scoped remediation diff payload",
    )
    submit_remediation_parser.add_argument(
        "--payload-file",
        type=Path,
        required=True,
        help="JSON payload containing dimension_token, base_digest, unified_diff, and issue_ids",
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
        _CMD_PROBE_COMPLETE,
        help="Sum probe issues and advance to Human Resolution",
    )
    sub.add_parser(
        _CMD_BEGIN_HUMAN_RESOLUTION,
        help="Begin Human Resolution phase; return dispatch list",
    )
    begin_human_dim = sub.add_parser(
        _CMD_BEGIN_DIMENSION_HUMAN,
        help="Begin Human Resolution for one dimension",
    )
    begin_human_dim.add_argument("--dim", required=True)
    submit_human_parser = sub.add_parser(
        _CMD_SUBMIT_HUMAN_RESOLUTION,
        help="Validate and publish a token-scoped human resolution payload",
    )
    submit_human_parser.add_argument(
        "--payload-file",
        type=Path,
        required=True,
        help="JSON payload containing dimension_token, base_digest, issue_ids, resolution_kind, and resolution",
    )
    check_human_dim = sub.add_parser(
        _CMD_CHECK_DIMENSION_HUMAN,
        help="Check Human Resolution for one dimension",
    )
    check_human_dim.add_argument("--dim", required=True)
    sub.add_parser(
        _CMD_HUMAN_RESOLUTION_COMPLETE,
        help="Complete Human Resolution phase",
    )
    sub.add_parser(
        _CMD_BEGIN_ARTIFACT_REMEDIATION,
        help="Begin Artifact Remediation phase; return dispatch list",
    )
    begin_art_dim = sub.add_parser(
        _CMD_BEGIN_DIMENSION_ARTIFACT,
        help="Begin Artifact Remediation for one dimension",
    )
    begin_art_dim.add_argument("--dim", required=True)
    check_art_dim = sub.add_parser(
        _CMD_CHECK_DIMENSION_ARTIFACT,
        help="Check Artifact Remediation for one dimension",
    )
    check_art_dim.add_argument("--dim", required=True)
    sub.add_parser(
        _CMD_ARTIFACT_REMEDIATION_COMPLETE,
        help="Complete Artifact Remediation phase",
    )
    sub.add_parser(
        _CMD_COMPLETE_ROUND,
        help="Finalize evaluation round and return summary payload",
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
        if args.command == _CMD_SUBMIT_REMEDIATION_DIFF:
            return _emit(
                submit_remediation_diff(
                    cycle_id,
                    project_root,
                    payload_file=args.payload_file,
                ),
            )
        if args.command == _CMD_CHECK_DIMENSION:
            return _emit(check_dimension(cycle_id, project_root, dim=args.dim))
        if args.command == _CMD_PROBE_COMPLETE:
            return _emit(probe_complete(cycle_id, project_root))
        if args.command == _CMD_BEGIN_HUMAN_RESOLUTION:
            return _emit(begin_human_resolution(cycle_id, project_root))
        if args.command == _CMD_BEGIN_DIMENSION_HUMAN:
            payload = begin_dimension_human_resolution(
                cycle_id,
                project_root,
                dim=args.dim,
            )
            if payload.get("ok") and "dispatch_input" in payload:
                print(payload["dispatch_input"])
                return 0
            return _emit(payload)
        if args.command == _CMD_SUBMIT_HUMAN_RESOLUTION:
            return _emit(
                submit_human_resolution(
                    cycle_id,
                    project_root,
                    payload_file=args.payload_file,
                ),
            )
        if args.command == _CMD_CHECK_DIMENSION_HUMAN:
            return _emit(
                check_dimension_human_resolution(
                    cycle_id,
                    project_root,
                    dim=args.dim,
                ),
            )
        if args.command == _CMD_HUMAN_RESOLUTION_COMPLETE:
            return _emit(human_resolution_complete(cycle_id, project_root))
        if args.command == _CMD_BEGIN_ARTIFACT_REMEDIATION:
            return _emit(begin_artifact_remediation(cycle_id, project_root))
        if args.command == _CMD_BEGIN_DIMENSION_ARTIFACT:
            payload = begin_dimension_artifact_remediation(
                cycle_id,
                project_root,
                dim=args.dim,
            )
            if payload.get("ok") and "dispatch_input" in payload:
                print(payload["dispatch_input"])
                return 0
            return _emit(payload)
        if args.command == _CMD_CHECK_DIMENSION_ARTIFACT:
            return _emit(
                check_dimension_artifact_remediation(
                    cycle_id,
                    project_root,
                    dim=args.dim,
                ),
            )
        if args.command == _CMD_ARTIFACT_REMEDIATION_COMPLETE:
            return _emit(artifact_remediation_complete(cycle_id, project_root))
        if args.command == _CMD_COMPLETE_ROUND:
            return _emit(complete_round(cycle_id, project_root))
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
