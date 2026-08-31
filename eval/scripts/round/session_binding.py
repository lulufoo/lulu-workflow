"""Session paths, corpus slice, and dimension dispatch for Eval."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import eval_control as ec
from corpus_schema import expand_corpus, resolve_dim_id
from corpus_snapshot import load_materialized_corpus, snapshot_dir
from evaluate_state_binding import (
    dispatch_dims_for_corpus,
    dispatch_legacy_for_corpus,
)
from evaluate_state_schema import parse_frontmatter_fields, parse_issue_counts
from eval_operation_record_schema import load_operation_records


def _load_corpus(cycle_id: str, project_root: Path):
    """Load the pinned round snapshot, or resolve only before admission."""
    es_path = _evaluate_state_path(cycle_id, project_root)
    if not es_path.is_file():
        return ec._adapter().resolve_eval_corpus(cycle_id, project_root)
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
    context = ec._handoff_context() or {}
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
        active_doc=ec._adapter().session_context(cycle_id, project_root).active_doc,
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
    return dispatch_dims_for_corpus(_load_corpus(cycle_id, project_root))


def _paths_from_handoff() -> dict[str, str] | None:
    context = ec._handoff_context()
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
        es_path = ec._adapter().resolve_evaluate_state_path(cycle_id, project_root)
    return ec._adapter().eval_paths(
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
    context = ec._handoff_context()
    if context:
        return Path(str(context["evaluate_state_path"]))
    return ec._adapter().resolve_evaluate_state_path(cycle_id, project_root)


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
        "upstream_baseline_ref": ec._upstream_baseline_ref(cycle_id, project_root),
        "cycle_type": ec._adapter().detect_cycle_type(cycle_id),
        "M": str(evaluate_round),
    }
    bind.update(ec._adapter().corpus_bind_extensions(cycle_id, project_root))
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


def _recompute_aggregate_counts(data: dict[str, str]) -> dict[str, str]:
    """Keep v7 aggregate counters equal to their issue-count projection."""
    updated = dict(data)
    counts = parse_issue_counts(updated.get("issue_counts", "{}"))
    updated["total_issues"] = str(sum(item["total"] for item in counts.values()))
    updated["resolved_issues"] = str(
        sum(item["resolved"] for item in counts.values()),
    )
    return updated


def _eval_capability() -> str:
    """Return the capability pinned by handoff, defaulting legacy adapters to full."""
    context = ec._handoff_context() or {}
    policy_context = context.get("policy_context")
    if isinstance(policy_context, dict):
        capability = policy_context.get("eval_capability")
        if capability in {"full-remediation", "probe-only"}:
            return str(capability)
    capability = context.get("eval_capability")
    if capability in {"full-remediation", "probe-only"}:
        return str(capability)
    return "full-remediation"


def _focus_phase(cycle_id: str, project_root: Path) -> str:
    return ec._adapter().session_context(cycle_id, project_root).focus_phase


def _operations_path(paths: dict[str, str]) -> Path:
    """Return the Script-owned runtime record path for this Eval round."""
    return Path(paths["evaluate_dir"]) / "eval-operations.json"


def _dimension_def(expanded_corpus: dict[str, Any], dim: str) -> dict[str, Any]:
    canonical = resolve_dim_id(expanded_corpus, dim)
    for item in expanded_corpus["dimensions"]:
        if item["id"] == canonical:
            return item
    raise ValueError(f"unknown dimension: {dim!r}")


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
