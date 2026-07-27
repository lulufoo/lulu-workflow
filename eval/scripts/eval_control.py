#!/usr/bin/env python3
"""Eval control for lulu-dev-workflow eval domain.

Owns mechanical writes to evaluate-state.md. Workflow-specific paths and state
transitions go through an injected WorkflowAdapter, loaded per-profile by
eval_entry.py (dynamic ``profile.eval.adapter_module`` / ``adapter_class``
loading, mirrors start.py's StartAdapter loading).

Invoke via eval_entry.py (e.g. `python3 eval_entry.py --workflow lulu-plan ...`).
Do not run this module directly as __main__.

Subcommands:
    init-round                  Initialize evaluate-state.md (internal; session_control)
    begin-eval-round            Enter focus evaluating (session stays Working) or next round
    begin-dimension             Mark dimension in_progress and return eval-runner inputs
    finish-dimension-probe      Validate review and mark dimension probed (locked)
    check-dimension             Read-only verify dimension probed after eval-runner
    probe-complete              Sum issues; advance fix_phase to artifact-remediation
    begin-artifact-remediation       Return artifact remediation dispatch list or skip
    begin-dimension-artifact-remediation  Per-dim artifact runner input (plain text)
    check-dimension-artifact-remediation  Reconcile one dim after artifact runner
    artifact-remediation-complete    Advance fix_phase to sot-remediation
    check-artifact-remediation       Alias for artifact-remediation-complete
    begin-sot-remediation            Return SoT remediation dispatch list or skip
    begin-dimension-sot-remediation  Per-dim SoT runner input (plain text)
    check-dimension-sot-remediation  Reconcile one dim after SoT runner
    sot-remediation-complete         Set fix_phase done / handle abandoned
    check-sot-remediation            Alias for sot-remediation-complete
    complete-round              Finalize evaluate-state and return summary payload
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

_EVAL_LIB = Path(__file__).resolve().parent
sys.path.insert(0, str(_EVAL_LIB))

_WORKFLOW_ROOT = _EVAL_LIB.parent.parent
_KERNEL_SCRIPTS = _WORKFLOW_ROOT / "compose" / "scripts"
if str(_KERNEL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_KERNEL_SCRIPTS))
import kernel_bootstrap  # noqa: E402

kernel_bootstrap.ensure_kernel_paths()
from review_io import (  # noqa: E402
    count_resolved,
    has_escalated,
    has_pending_sot,
    parse_review_file,
    pending_artifact_rows,
    pending_sot_rows,
)
from review_schema import validate_review_file  # noqa: E402
from corpus_schema import (  # noqa: E402
    expand_corpus,
    resolve_dim_id,
)
from evaluate_state_schema import (  # noqa: E402
    all_dims_at_least,
    is_v3_state,
    load_evaluate_state,
    parse_dimension_status,
    parse_issue_counts,
    patch_issue_count,
    save_evaluate_state,
    sum_issue_totals,
)
from contextvars import ContextVar

from evaluate_state_ops import (  # noqa: E402
    build_initial_evaluate_state_for_corpus,
    dimension_status_legacy_map,
    dispatch_legacy_for_corpus,
    init_evaluate_state_for_corpus,
    merge_current_dimension,
    save_evaluate_state_locked,
)
from workflow_adapter import WorkflowAdapter  # noqa: E402

_ADAPTER_CTX: ContextVar[WorkflowAdapter | None] = ContextVar("workflow_adapter", default=None)
_WORKFLOW_ID_CTX: ContextVar[str | None] = ContextVar("workflow_id", default=None)


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
            "WORKFLOW_ID not set; invoke via eval_entry.py (--workflow)",
        )
    return workflow_id


def _upstream_baseline_ref(cycle_id: str, project_root: Path) -> str:
    """Upstream baseline doc path from the active workflow adapter session context."""
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
    """Return legacy eval dimension dispatch (e2/e3/e4) for eval-rules."""
    return dispatch_legacy_for_corpus(_load_corpus(cycle_id, project_root))


def _dispatch_canonical(cycle_id: str, project_root: Path) -> list[str]:
    """Return canonical dimension ids from session EvalCorpus."""
    from evaluate_state_ops import dispatch_dims_for_corpus

    return dispatch_dims_for_corpus(_load_corpus(cycle_id, project_root))


def _eval_dir(
    cycle_id: str,
    project_root: Path,
    *,
    active_doc: int,
    evaluate_round: int,
    es_path: Path | None = None,
) -> Path:
    if es_path is None:
        es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
    paths = _adapter().eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    return Path(paths["evaluate_dir"])


_CMD_INIT_ROUND = "init-round"
_CMD_BEGIN_EVAL_ROUND = "begin-eval-round"
_CMD_BEGIN_DIMENSION = "begin-dimension"
_CMD_FINISH_DIMENSION_PROBE = "finish-dimension-probe"
_CMD_CHECK_DIMENSION = "check-dimension"
_CMD_PROBE_COMPLETE = "probe-complete"
_CMD_BEGIN_ARTIFACT_REMEDIATION = "begin-artifact-remediation"
_CMD_BEGIN_DIMENSION_ARTIFACT = "begin-dimension-artifact-remediation"
_CMD_CHECK_DIMENSION_ARTIFACT = "check-dimension-artifact-remediation"
_CMD_ARTIFACT_REMEDIATION_COMPLETE = "artifact-remediation-complete"
_CMD_CHECK_ARTIFACT_REMEDIATION = "check-artifact-remediation"
_CMD_BEGIN_SOT_REMEDIATION = "begin-sot-remediation"
_CMD_BEGIN_DIMENSION_SOT = "begin-dimension-sot-remediation"
_CMD_CHECK_DIMENSION_SOT = "check-dimension-sot-remediation"
_CMD_SOT_REMEDIATION_COMPLETE = "sot-remediation-complete"
_CMD_CHECK_SOT_REMEDIATION = "check-sot-remediation"
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


_ENTRY_V3_KEYS = (
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


def _bind_vars(
    cycle_id: str,
    state: dict[str, str],
    paths: dict[str, str],
    evaluate_round: int,
    *,
    project_root: Path,
) -> dict[str, str]:
    bind = {
        "compose_doc": paths["compose_doc"],
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


def _eval_paths(
    cycle_id: str,
    project_root: Path,
    *,
    active_doc: int,
    evaluate_round: int,
    es_path: Path,
) -> dict[str, str]:
    return _adapter().eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )


def _validate_evaluate_state_for_session(
    eval_data: dict[str, str],
    cycle_id: str,
    project_root: Path,
) -> str | None:
    """Return error reason when evaluate-state does not match session at entry."""
    if not is_v3_state(eval_data):
        return (
            "evaluate-state version 1/2 is not supported; "
            "start a new eval round (Re-evaluate)."
        )
    if eval_data.get("phase") != "evaluate":
        return f"phase is {eval_data.get('phase')!r}, expected 'evaluate'."
    try:
        expected = build_initial_evaluate_state_for_corpus(
            _load_corpus(cycle_id, project_root),
            cycle_type=_adapter().detect_cycle_type(cycle_id),
        )
    except ValueError as exc:
        return str(exc)
    for key in _ENTRY_V3_KEYS:
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
    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
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

    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
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

    if not is_v3_state(eval_data):
        return _failure(
            "",
            "evaluate-state version 1/2 is not supported; start a new eval round.",
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
    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
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
    """Increment evaluate_round, re-init evaluate-state, return loop payload."""
    try:
        evaluate_round = int(state.get("evaluate_round", "0")) + 1
    except ValueError:
        evaluate_round = 1

    merged = dict(state)
    merged["evaluate_round"] = str(evaluate_round)
    _adapter().save_workflow_state(cycle_id, project_root, merged, merge=False)
    init_round(cycle_id, project_root, mode=mode)
    return build_eval_loop_payload(cycle_id, project_root)


def begin_eval_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Enter focus evaluating or start next eval round; return payload."""
    ws_path = _adapter().resolve_workflow_state_path(cycle_id, project_root)
    state = _adapter().load_workflow_state(cycle_id, project_root)
    current = state["current_state"]
    mode = state["mode"]
    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)

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

        if not is_v3_state(eval_data):
            return _failure(
                _CMD_BEGIN_EVAL_ROUND,
                "evaluate-state version 1/2 is not supported; start a new eval round.",
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

    state = _adapter().load_workflow_state(cycle_id, project_root)
    mode = state["mode"]

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


def _format_runner_dispatch_input(runner_input: dict[str, str]) -> str:
    lines = [
        f"WORKFLOW_ID:           {runner_input['WORKFLOW_ID']}",
        f"DIMENSION_ID:          {runner_input['DIMENSION_ID']}",
        f"DIMENSION:             {runner_input['DIMENSION']}",
        f"DIMENSION_LABEL:       {runner_input['DIMENSION_LABEL']}",
        f"CYCLE_ID:              {runner_input['CYCLE_ID']}",
        f"CYCLE_TYPE:            {runner_input['CYCLE_TYPE']}",
        f"EVAL_TARGET_PATH:      {runner_input['EVAL_TARGET_PATH']}",
        f"REMEDIATION_TARGET_PATH: {runner_input['REMEDIATION_TARGET_PATH']}",
        f"EVALUATE_STATE_PATH:   {runner_input['EVALUATE_STATE_PATH']}",
        f"EVALUATE_DIR:          {runner_input['EVALUATE_DIR']}",
        f"REVIEW_OUTPUT_PATH:    {runner_input['REVIEW_OUTPUT_PATH']}",
        f"PROJECT_ROOT:          {runner_input['PROJECT_ROOT']}",
        f"SOTS_JSON:             {runner_input['SOTS_JSON']}",
        f"METHOD_JSON:           {runner_input['METHOD_JSON']}",
        f"METHOD_FOCUS:          {runner_input['METHOD_FOCUS']}",
    ]
    upstream_baseline_ref = runner_input.get("UPSTREAM_BASELINE_REF", "")
    if upstream_baseline_ref:
        lines.append(f"UPSTREAM_BASELINE_REF: {upstream_baseline_ref}")
    return "\n".join(lines)


def _dimension_def(expanded_corpus: dict[str, Any], dim: str) -> dict[str, Any]:
    canonical = resolve_dim_id(expanded_corpus, dim)
    for item in expanded_corpus["dimensions"]:
        if item["id"] == canonical:
            return item
    raise ValueError(f"unknown dimension: {dim!r}")


def _build_runner_input(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
    state: dict[str, str],
    paths: dict[str, str],
    evaluate_round: int,
) -> dict[str, str]:
    expanded = _expanded_corpus(
        cycle_id,
        state,
        paths,
        evaluate_round,
        project_root=project_root,
    )
    dim_def = _dimension_def(expanded, dim)
    dispatch_key = str(dim_def.get("legacy_alias") or dim_def["id"])
    sots = dim_def.get("sots", [])
    method = dim_def.get("method", {})
    runner_input: dict[str, str] = {
        "WORKFLOW_ID": _workflow_id(),
        "DIMENSION_ID": str(dim_def["id"]),
        "DIMENSION": dispatch_key,
        "DIMENSION_LABEL": str(dim_def["label"]),
        "CYCLE_ID": cycle_id,
        "CYCLE_TYPE": _adapter().detect_cycle_type(cycle_id),
        "EVAL_TARGET_PATH": str(dim_def["eval_target"]["path"]),
        "REMEDIATION_TARGET_PATH": str(dim_def["remediation_target"]["path"]),
        "EVALUATE_STATE_PATH": paths["evaluate_state"],
        "EVALUATE_DIR": paths["evaluate_dir"],
        "REVIEW_OUTPUT_PATH": str(dim_def["review"]["output_path"]),
        "PROJECT_ROOT": project_root.resolve().as_posix(),
        "SOTS_JSON": json.dumps(sots, ensure_ascii=False, separators=(",", ":")),
        "METHOD_JSON": json.dumps(method, ensure_ascii=False, separators=(",", ":")),
        "METHOD_FOCUS": str(method.get("focus", "")),
    }
    for sot in sots:
        if sot.get("kind") == "url":
            ref = str(sot.get("ref", ""))
            if ref and ref != paths["compose_doc"]:
                runner_input["UPSTREAM_BASELINE_REF"] = ref
                break
    if "UPSTREAM_BASELINE_REF" not in runner_input:
        pref = _upstream_baseline_ref(cycle_id, project_root)
        if pref and any(s.get("kind") == "url" for s in sots):
            runner_input["UPSTREAM_BASELINE_REF"] = pref
    return runner_input


def init_round(
    cycle_id: str,
    project_root: Path,
    *,
    mode: str | None = None,
) -> dict[str, Any]:
    """Initialize evaluate-state.md for the current active revision."""
    if mode is None:
        mode = _adapter().load_workflow_state(cycle_id, project_root)["mode"]
    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
    corpus = _load_corpus(cycle_id, project_root)
    cycle_type = _adapter().detect_cycle_type(cycle_id)
    init_evaluate_state_for_corpus(es_path, corpus, cycle_type=cycle_type)
    return _success(
        _CMD_INIT_ROUND,
        mode=mode,
        path=es_path.resolve().as_posix(),
    )


def begin_dimension(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Mark dimension in_progress and return eval-probe-runner input block."""
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

    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )

    corpus = _load_corpus(cycle_id, project_root)

    def _patch(data: dict[str, str]) -> dict[str, str]:
        return merge_current_dimension(data, dim, "in_progress", corpus=corpus)

    save_evaluate_state_locked(es_path, _patch)

    runner_input = _build_runner_input(
        cycle_id,
        project_root,
        dim=dim,
        state=state,
        paths=paths,
        evaluate_round=evaluate_round,
    )
    return _success(
        _CMD_BEGIN_DIMENSION,
        dim=dim,
        current_state=state["current_state"],
        runner_input=runner_input,
        dispatch_input=_format_runner_dispatch_input(runner_input),
    )


def finish_dimension_probe(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Validate review file and mark dimension probed (locked write)."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_FINISH_DIMENSION_PROBE
        ctx["dim"] = dim
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if not _dispatch_dim_allowed(cycle_id, project_root, dim):
        return _failure(
            _CMD_FINISH_DIMENSION_PROBE,
            f"invalid dim: {dim!r} (not in corpus for mode {mode!r}).",
            dim=dim,
        )

    eval_dir = _eval_dir(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
    )
    review_path = _review_path_from_context(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
        dim=dim,
    )
    validation_errors = validate_review_file(review_path, phase="probe")
    if validation_errors:
        return _failure(
            _CMD_FINISH_DIMENSION_PROBE,
            "; ".join(validation_errors),
            dim=dim,
            review_path=review_path.as_posix(),
        )

    rows = parse_review_file(review_path)
    total_issues = str(len(rows))
    dim_id = _canonical_dim(cycle_id, project_root, dim)

    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)

    corpus = _load_corpus(cycle_id, project_root)

    def _patch(data: dict[str, str]) -> dict[str, str]:
        updated = merge_current_dimension(data, dim, "probed", corpus=corpus)
        return patch_issue_count(updated, dim_id, total=total_issues)

    save_evaluate_state_locked(es_path, _patch)

    return _success(
        _CMD_FINISH_DIMENSION_PROBE,
        dim=dim,
        outcome="probed",
        total_issues=total_issues,
        review_path=review_path.resolve().as_posix(),
    )


def check_dimension(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Read-only verify dimension probed after eval-probe-runner."""
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
                "expected 'probed' (runner forgot finish-dimension-probe?)."
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


def probe_complete(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Sum total_issues and advance fix_phase to artifact-remediation."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_PROBE_COMPLETE
        return ctx

    state, _ws_path, eval_data, _evaluate_round, _active_doc, mode = ctx
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

    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
    save_evaluate_state(
        es_path,
        {
            "total_issues": str(total),
            "fix_phase": "artifact-remediation",
        },
    )

    return _success(
        _CMD_PROBE_COMPLETE,
        fix_phase="artifact-remediation",
        total_issues=str(total),
        current_state=state["current_state"],
    )


def _build_remediation_runner_input(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
    state: dict[str, str],
    paths: dict[str, str],
    evaluate_round: int,
) -> dict[str, str]:
    expanded = _expanded_corpus(
        cycle_id,
        state,
        paths,
        evaluate_round,
        project_root=project_root,
    )
    dim_def = _dimension_def(expanded, dim)
    dispatch_key = str(dim_def.get("legacy_alias") or dim_def["id"])
    runner_input: dict[str, str] = {
        "WORKFLOW_ID": _workflow_id(),
        "DIMENSION_ID": str(dim_def["id"]),
        "DIMENSION": dispatch_key,
        "DIMENSION_LABEL": str(dim_def["label"]),
        "CYCLE_ID": cycle_id,
        "CYCLE_TYPE": _adapter().detect_cycle_type(cycle_id),
        "REMEDIATION_TARGET_PATH": str(dim_def["remediation_target"]["path"]),
        "EVALUATE_DIR": paths["evaluate_dir"],
        "EVALUATE_STATE_PATH": paths["evaluate_state"],
        "REVIEW_OUTPUT_PATH": str(dim_def["review"]["output_path"]),
        "EVALUATE_ROUND": str(evaluate_round),
        "PROJECT_ROOT": project_root.resolve().as_posix(),
    }
    upstream_baseline_ref = _upstream_baseline_ref(cycle_id, project_root)
    if upstream_baseline_ref:
        runner_input["UPSTREAM_BASELINE_REF"] = upstream_baseline_ref
    return runner_input


def _format_remediation_dispatch_input(data: dict[str, str]) -> str:
    lines = [
        f"WORKFLOW_ID:           {data['WORKFLOW_ID']}",
        f"DIMENSION_ID:          {data['DIMENSION_ID']}",
        f"DIMENSION:             {data['DIMENSION']}",
        f"DIMENSION_LABEL:       {data['DIMENSION_LABEL']}",
        f"CYCLE_ID:              {data['CYCLE_ID']}",
        f"CYCLE_TYPE:            {data['CYCLE_TYPE']}",
        f"REMEDIATION_TARGET_PATH: {data['REMEDIATION_TARGET_PATH']}",
        f"EVALUATE_DIR:          {data['EVALUATE_DIR']}",
        f"EVALUATE_STATE_PATH:   {data['EVALUATE_STATE_PATH']}",
        f"REVIEW_OUTPUT_PATH:    {data['REVIEW_OUTPUT_PATH']}",
        f"EVALUATE_ROUND:        {data['EVALUATE_ROUND']}",
        f"PROJECT_ROOT:          {data['PROJECT_ROOT']}",
    ]
    if data.get("UPSTREAM_BASELINE_REF"):
        lines.append(f"UPSTREAM_BASELINE_REF: {data['UPSTREAM_BASELINE_REF']}")
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


def _dims_with_pending_sot(
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
        if pending_sot_rows(rows):
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

    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    runner_input = _build_remediation_runner_input(
        cycle_id,
        project_root,
        dim=dim,
        state=state,
        paths=paths,
        evaluate_round=evaluate_round,
    )
    return _success(
        _CMD_BEGIN_DIMENSION_ARTIFACT,
        dim=dim,
        current_state=state["current_state"],
        runner_input=runner_input,
        dispatch_input=_format_remediation_dispatch_input(runner_input),
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
    if not has_pending_sot(rows):
        merged = merge_current_dimension(merged, dim, "complete", corpus=corpus)

    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
    save_evaluate_state(
        es_path,
        {
            "issue_counts": merged["issue_counts"],
            "dimension_status": merged["dimension_status"],
        },
    )

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
    """Advance fix_phase to sot-remediation when artifact phase is done."""
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

    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
    save_evaluate_state(
        es_path,
        {
            "resolved_issues": str(resolved_total),
            "fix_phase": "sot-remediation",
        },
    )

    return _success(
        _CMD_ARTIFACT_REMEDIATION_COMPLETE,
        fix_phase="sot-remediation",
        current_state=state["current_state"],
        resolved_issues=str(resolved_total),
    )


def check_artifact_remediation(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Legacy alias: advance artifact remediation phase (prefer per-dim + complete)."""
    return artifact_remediation_complete(cycle_id, project_root)


def begin_sot_remediation(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Return SoT remediation dispatch list or skip when no pending SOT-* rows."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_BEGIN_SOT_REMEDIATION
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if eval_data.get("fix_phase") != "sot-remediation":
        return _failure(
            _CMD_BEGIN_SOT_REMEDIATION,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'sot-remediation'."
            ),
            current_state=state["current_state"],
        )

    pending_dims = _dims_with_pending_sot(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
    )
    if not pending_dims:
        return _success(
            _CMD_BEGIN_SOT_REMEDIATION,
            skip=True,
            dispatch=[],
            dimension_dispatch=eval_data.get("dimension_dispatch", "parallel"),
            current_state=state["current_state"],
        )

    return _success(
        _CMD_BEGIN_SOT_REMEDIATION,
        skip=False,
        dispatch=pending_dims,
        dimension_dispatch=eval_data.get("dimension_dispatch", "parallel"),
        current_state=state["current_state"],
        pending_count=len(pending_dims),
    )


def begin_dimension_sot_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Return per-dimension SoT remediation dispatch input (plain text)."""
    if not dim.strip():
        return _failure(_CMD_BEGIN_DIMENSION_SOT, "invalid dim: empty string")

    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_BEGIN_DIMENSION_SOT
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if not _dispatch_dim_allowed(cycle_id, project_root, dim):
        return _failure(
            _CMD_BEGIN_DIMENSION_SOT,
            f"invalid dim: {dim!r} (not in corpus for mode {mode!r}).",
        )
    if eval_data.get("fix_phase") != "sot-remediation":
        return _failure(
            _CMD_BEGIN_DIMENSION_SOT,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'sot-remediation'."
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
    if not pending_sot_rows(rows):
        return _failure(
            _CMD_BEGIN_DIMENSION_SOT,
            f"no pending SOT-* rows for dim {dim!r}.",
            dim=dim,
        )

    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
    paths = _eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )
    runner_input = _build_remediation_runner_input(
        cycle_id,
        project_root,
        dim=dim,
        state=state,
        paths=paths,
        evaluate_round=evaluate_round,
    )
    return _success(
        _CMD_BEGIN_DIMENSION_SOT,
        dim=dim,
        current_state=state["current_state"],
        runner_input=runner_input,
        dispatch_input=_format_remediation_dispatch_input(runner_input),
    )


def check_dimension_sot_remediation(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Reconcile SOT-* rows for one dimension after SoT runner."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_CHECK_DIMENSION_SOT
        ctx["dim"] = dim
        ctx["abandoned"] = False
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if not _dispatch_dim_allowed(cycle_id, project_root, dim):
        return _failure(
            _CMD_CHECK_DIMENSION_SOT,
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
            _CMD_CHECK_DIMENSION_SOT,
            "; ".join(errors),
            dim=dim,
            abandoned=False,
        )

    rows = parse_review_file(review_path)
    if pending_sot_rows(rows):
        return _failure(
            _CMD_CHECK_DIMENSION_SOT,
            f"pending SOT-* rows remain for dim {dim!r}.",
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
    corpus = _load_corpus(cycle_id, project_root)
    dim_map = dimension_status_legacy_map(eval_data, corpus=corpus)
    if dim_map.get(dim) == "probed":
        merged = merge_current_dimension(merged, dim, "complete", corpus=corpus)

    patch: dict[str, str] = {
        "issue_counts": merged["issue_counts"],
        "dimension_status": merged["dimension_status"],
    }
    if escalated:
        patch["eval_status"] = "abandoned"

    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
    save_evaluate_state(es_path, patch)

    return _success(
        _CMD_CHECK_DIMENSION_SOT,
        dim=dim,
        abandoned=escalated,
        current_state=state["current_state"],
    )


def sot_remediation_complete(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Finalize SoT remediation phase; set fix_phase done."""
    ctx = _load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = _CMD_SOT_REMEDIATION_COMPLETE
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    dispatch = dispatch_list(cycle_id, project_root)

    if eval_data.get("fix_phase") != "sot-remediation":
        return _failure(
            _CMD_SOT_REMEDIATION_COMPLETE,
            (
                f"fix_phase is {eval_data.get('fix_phase')!r}, "
                "expected 'sot-remediation'."
            ),
            current_state=state["current_state"],
        )

    if eval_data.get("eval_status") == "abandoned":
        es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
        save_evaluate_state(es_path, {"fix_phase": "done"})
        return _success(
            _CMD_SOT_REMEDIATION_COMPLETE,
            fix_phase="done",
            abandoned=True,
            current_state=state["current_state"],
        )

    for dim in dispatch:
        rows = _review_rows_for_dim(
            cycle_id,
            project_root,
            state=state,
            evaluate_round=evaluate_round,
            active_doc=active_doc,
            dim=dim,
        )
        if pending_sot_rows(rows):
            return _failure(
                _CMD_SOT_REMEDIATION_COMPLETE,
                f"pending SOT-* rows remain for dim {dim!r}.",
                current_state=state["current_state"],
            )

    resolved_total = sum(
        count_resolved(
            _review_rows_for_dim(
                cycle_id,
                project_root,
                state=state,
                evaluate_round=evaluate_round,
                active_doc=active_doc,
                dim=dim,
            ),
        )
        for dim in dispatch
    )

    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
    save_evaluate_state(
        es_path,
        {
            "resolved_issues": str(resolved_total),
            "fix_phase": "done",
        },
    )
    eval_data_after = load_evaluate_state(es_path)
    if not all_dims_at_least(eval_data_after, _dispatch_canonical(cycle_id, project_root), "complete"):
        corpus = _load_corpus(cycle_id, project_root)
        dim_map = dimension_status_legacy_map(eval_data_after, corpus=corpus)
        incomplete = [
            dim for dim in dispatch if dim_map.get(dim) != "complete"
        ]
        return _failure(
            _CMD_SOT_REMEDIATION_COMPLETE,
            (
                f"dispatch dimensions not complete after SoT remediation: "
                f"{incomplete!r}."
            ),
            current_state=state["current_state"],
            incomplete_dims=incomplete,
        )

    return _success(
        _CMD_SOT_REMEDIATION_COMPLETE,
        fix_phase="done",
        abandoned=False,
        current_state=state["current_state"],
        resolved_issues=str(resolved_total),
    )


def check_sot_remediation(
    cycle_id: str,
    project_root: Path,
) -> dict[str, Any]:
    """Legacy alias: finalize SoT remediation (prefer per-dim + complete)."""
    return sot_remediation_complete(cycle_id, project_root)


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

    es_path = _adapter().resolve_evaluate_state_path(cycle_id, project_root)
    save_evaluate_state(
        es_path,
        {
            "eval_status": "done",
            "fix_severity": fix_severity,
            "fix_severity_reason": fix_severity_reason,
        },
    )
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
        required=True,
        help="Workflow id (e.g. lulu-plan)",
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

    finish_parser = sub.add_parser(
        _CMD_FINISH_DIMENSION_PROBE,
        help="Validate review and mark dimension probed",
    )
    finish_parser.add_argument(
        "--dim",
        required=True,
        help="Dimension dispatch key (legacy e1/e2/e3 or canonical id)",
    )

    check_parser = sub.add_parser(
        _CMD_CHECK_DIMENSION,
        help="Read single-dimension outcome after eval-probe-runner",
    )
    check_parser.add_argument(
        "--dim",
        required=True,
        help="Dimension dispatch key (legacy e1/e2/e3 or canonical id)",
    )

    sub.add_parser(
        _CMD_PROBE_COMPLETE,
        help="Sum probe issues and advance to artifact remediation",
    )
    sub.add_parser(
        _CMD_BEGIN_ARTIFACT_REMEDIATION,
        help="Begin artifact remediation phase; return dispatch list",
    )
    begin_art_dim = sub.add_parser(
        _CMD_BEGIN_DIMENSION_ARTIFACT,
        help="Begin artifact remediation for one dimension",
    )
    begin_art_dim.add_argument("--dim", required=True)

    check_art_dim = sub.add_parser(
        _CMD_CHECK_DIMENSION_ARTIFACT,
        help="Check artifact remediation for one dimension",
    )
    check_art_dim.add_argument("--dim", required=True)

    sub.add_parser(
        _CMD_ARTIFACT_REMEDIATION_COMPLETE,
        help="Complete artifact remediation phase",
    )
    sub.add_parser(
        _CMD_CHECK_ARTIFACT_REMEDIATION,
        help="Alias: artifact-remediation-complete",
    )
    sub.add_parser(
        _CMD_BEGIN_SOT_REMEDIATION,
        help="Begin SoT remediation phase; return dispatch list",
    )
    begin_sot_dim = sub.add_parser(
        _CMD_BEGIN_DIMENSION_SOT,
        help="Begin SoT remediation for one dimension",
    )
    begin_sot_dim.add_argument("--dim", required=True)

    check_sot_dim = sub.add_parser(
        _CMD_CHECK_DIMENSION_SOT,
        help="Check SoT remediation for one dimension",
    )
    check_sot_dim.add_argument("--dim", required=True)

    sub.add_parser(
        _CMD_SOT_REMEDIATION_COMPLETE,
        help="Complete SoT remediation phase",
    )
    sub.add_parser(
        _CMD_CHECK_SOT_REMEDIATION,
        help="Alias: sot-remediation-complete",
    )
    sub.add_parser(
        _CMD_COMPLETE_ROUND,
        help="Finalize evaluation round and return summary payload",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def run_eval(args: argparse.Namespace, adapter: WorkflowAdapter) -> int:
    """Run eval subcommand with an injected WorkflowAdapter (stage entrypoint)."""
    project_root = args.project_root.resolve()
    cycle_id = args.cycle_id.strip()
    adapter_token = _ADAPTER_CTX.set(adapter)
    workflow_token = _WORKFLOW_ID_CTX.set(args.workflow.strip())

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
        if args.command == _CMD_FINISH_DIMENSION_PROBE:
            return _emit(
                finish_dimension_probe(cycle_id, project_root, dim=args.dim),
            )
        if args.command == _CMD_CHECK_DIMENSION:
            return _emit(check_dimension(cycle_id, project_root, dim=args.dim))
        if args.command == _CMD_PROBE_COMPLETE:
            return _emit(probe_complete(cycle_id, project_root))
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
        if args.command == _CMD_CHECK_ARTIFACT_REMEDIATION:
            return _emit(check_artifact_remediation(cycle_id, project_root))
        if args.command == _CMD_BEGIN_SOT_REMEDIATION:
            return _emit(begin_sot_remediation(cycle_id, project_root))
        if args.command == _CMD_BEGIN_DIMENSION_SOT:
            payload = begin_dimension_sot_remediation(
                cycle_id,
                project_root,
                dim=args.dim,
            )
            if payload.get("ok") and "dispatch_input" in payload:
                print(payload["dispatch_input"])
                return 0
            return _emit(payload)
        if args.command == _CMD_CHECK_DIMENSION_SOT:
            return _emit(
                check_dimension_sot_remediation(
                    cycle_id,
                    project_root,
                    dim=args.dim,
                ),
            )
        if args.command == _CMD_SOT_REMEDIATION_COMPLETE:
            return _emit(sot_remediation_complete(cycle_id, project_root))
        if args.command == _CMD_CHECK_SOT_REMEDIATION:
            return _emit(check_sot_remediation(cycle_id, project_root))
        if args.command == _CMD_COMPLETE_ROUND:
            return _emit(complete_round(cycle_id, project_root))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        _ADAPTER_CTX.reset(adapter_token)
        _WORKFLOW_ID_CTX.reset(workflow_token)

    return 1


def main() -> int:
    print(
        "错误：请通过 eval_entry.py 调用（例如 "
        "python3 eval_entry.py --workflow lulu-plan ...）。",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
