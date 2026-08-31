#!/usr/bin/env python3
"""Eval probe control — dimension probe commands.

Owns begin/read/submit/check for the probe family, plus read-unit-view.
eval_control.run_eval forwards here. Invoke via eval_entry.py. Not __main__.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import eval_control as ec
import evaluate_context
import operation_recovery
import review_binding
import session_binding
from eval_target_units import units_from_eval_target

_PROBE_PAYLOAD_KEYS = frozenset({"dimension_token", "findings"})
_FINDING_REQUIRED_KEYS = frozenset(
    {"id", "root_cause", "location", "severity", "evidence", "description"},
)
_FINDING_OPTIONAL_KEYS = frozenset({"sot_ref", "realign_gate"})


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


def _load_authorized_target(
    cycle_id: str,
    project_root: Path,
    *,
    dimension_token: str,
    command: str,
) -> dict[str, Any]:
    """Load a token-authorized B snapshot, or a failure payload."""
    if not dimension_token.strip():
        return ec._failure(command, "invalid dimension_token: empty string")
    ctx = evaluate_context._load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = command
        return ctx
    _state, _ws_path, eval_data, evaluate_round, active_doc, _mode = ctx
    paths = session_binding._eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=session_binding._evaluate_state_path(cycle_id, project_root),
    )
    try:
        snapshot = ec.read_target_snapshot(
            operations_path=session_binding._operations_path(paths),
            dimension_token=dimension_token,
        )
    except ValueError as exc:
        return ec._failure(command, str(exc))
    return {
        "ok": True,
        "eval_data": eval_data,
        "snapshot": snapshot,
    }


def begin_dimension(
    cycle_id: str,
    project_root: Path,
    *,
    dim: str,
) -> dict[str, Any]:
    """Mark a dimension in progress and return dimension-probe-runner input."""
    if not dim.strip():
        return ec._failure(
            ec._CMD_BEGIN_DIMENSION,
            "invalid dim: empty string",
        )

    ctx = evaluate_context._load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = ec._CMD_BEGIN_DIMENSION
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if not session_binding._dispatch_dim_allowed(cycle_id, project_root, dim):
        return ec._failure(
            ec._CMD_BEGIN_DIMENSION,
            f"invalid dim: {dim!r} (not in corpus for mode {mode!r}).",
        )

    if eval_data.get("eval_phase") != "probe":
        return ec._failure(
            ec._CMD_BEGIN_DIMENSION,
            f"eval_phase is {eval_data.get('eval_phase')!r}, expected 'probe'.",
            current_state=state["current_state"],
        )

    es_path = session_binding._evaluate_state_path(cycle_id, project_root)
    paths = session_binding._eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=es_path,
    )

    corpus = session_binding._load_corpus(cycle_id, project_root)
    canonical_dim = session_binding._canonical_dim(cycle_id, project_root, dim)
    dimension_status = ec.parse_dimension_status(eval_data["dimension_status"])
    if dimension_status.get(canonical_dim) == "skipped":
        reasons = ec.parse_skip_reason(eval_data.get("skip_reason", "{}"))
        return ec._success(
            ec._CMD_BEGIN_DIMENSION,
            dim=dim,
            skip=True,
            skip_reason=reasons.get(canonical_dim, ""),
            current_state=state["current_state"],
        )
    if dimension_status.get(canonical_dim) != "pending":
        return ec._failure(
            ec._CMD_BEGIN_DIMENSION,
            f"dimension is not pending: {canonical_dim!r}",
            dim=dim,
        )

    expanded = session_binding._expanded_corpus(
        cycle_id,
        state,
        paths,
        evaluate_round,
        project_root=project_root,
    )
    dim_def = session_binding._dimension_def(expanded, dim)
    try:
        operation_ctx = ec.issue_probe_context(
            operations_path=session_binding._operations_path(paths),
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
        return ec._failure(ec._CMD_BEGIN_DIMENSION, str(exc), dim=dim)

    def _patch(data: dict[str, str]) -> dict[str, str]:
        updated = ec.merge_current_dimension(data, dim, "probing", corpus=corpus)
        if paths.get("session_key"):
            updated["focus_l"] = str(paths["session_key"])
        updated["evaluate_round"] = str(evaluate_round)
        return updated

    error = evaluate_context._commit_staged_evaluate_state(
        cycle_id,
        project_root,
        update=_patch,
    )
    if error is not None:
        try:
            ec.discard_operation_context(
                operations_path=session_binding._operations_path(paths),
                dimension_token=operation_ctx["dimension_token"],
            )
        except (OSError, ValueError):
            pass
        return ec._failure(ec._CMD_BEGIN_DIMENSION, error, dim=dim)

    return ec._success(
        ec._CMD_BEGIN_DIMENSION,
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
    loaded = _load_authorized_target(
        cycle_id,
        project_root,
        dimension_token=dimension_token,
        command=ec._CMD_READ_B_SNAPSHOT,
    )
    if not loaded.get("ok") or "snapshot" not in loaded:
        return loaded
    snapshot = loaded["snapshot"]
    return ec._success(
        ec._CMD_READ_B_SNAPSHOT,
        dimension_token=dimension_token,
        round_token=loaded["eval_data"]["round_token"],
        target_digest=snapshot["digest"],
        content=snapshot["content"],
    )


def read_unit_view_cmd(
    cycle_id: str,
    project_root: Path,
    *,
    dimension_token: str,
) -> dict[str, Any]:
    """Return chapter units from the token-authorized EvalTarget B."""
    loaded = _load_authorized_target(
        cycle_id,
        project_root,
        dimension_token=dimension_token,
        command=ec._CMD_READ_UNIT_VIEW,
    )
    if not loaded.get("ok") or "snapshot" not in loaded:
        return loaded
    snapshot = loaded["snapshot"]
    view = units_from_eval_target(str(snapshot["content"]))
    return ec._success(
        ec._CMD_READ_UNIT_VIEW,
        dimension_token=dimension_token,
        round_token=loaded["eval_data"]["round_token"],
        target_digest=snapshot["digest"],
        shape=view["shape"],
        containers=view["containers"],
        empty=view["empty"],
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
        return ec._failure(
            ec._CMD_READ_EVIDENCE_SNAPSHOT,
            "invalid dimension_token: empty string",
        )
    if not evidence_ref.strip():
        return ec._failure(
            ec._CMD_READ_EVIDENCE_SNAPSHOT,
            "invalid evidence_ref: empty string",
        )
    ctx = evaluate_context._load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = ec._CMD_READ_EVIDENCE_SNAPSHOT
        return ctx
    _state, _ws_path, _eval_data, evaluate_round, active_doc, _mode = ctx
    paths = session_binding._eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=session_binding._evaluate_state_path(cycle_id, project_root),
    )
    try:
        snapshot = ec.read_evidence_snapshot(
            operations_path=session_binding._operations_path(paths),
            dimension_token=dimension_token,
            evidence_ref=evidence_ref,
        )
    except ValueError as exc:
        return ec._failure(ec._CMD_READ_EVIDENCE_SNAPSHOT, str(exc))
    return ec._success(
        ec._CMD_READ_EVIDENCE_SNAPSHOT,
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
    content = ec.render_review_header(
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
            "handling_mode": review_binding.handling_mode_for_issue(
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
    errors = ec.validate_review_content(content, phase="probe")
    if errors:
        raise ValueError(f"generated review invalid: {'; '.join(errors)}")
    return content


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
        ec._atomic_write_text(formal_review_path, content)
        return None

    staging = Path(str(paths["write_staging_dir"]))
    staged = staging / formal_review_path.name
    ec._atomic_write_text(staged, content)
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest = ec.build_artifact_manifest_v2(
        lease_id=lease_id,
        session_key=str(paths.get("session_key", "")),
        evaluate_round=evaluate_round,
        staged_relative_path=formal_review_path.name,
        final_relative_path=formal_review_path.name,
        artifact_digest=digest,
    )
    result = ec._adapter().commit_eval_artifacts(
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
        return ec._failure(ec._CMD_SUBMIT_PROBE_FINDINGS, str(exc))

    ctx = evaluate_context._load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = ec._CMD_SUBMIT_PROBE_FINDINGS
        return ctx
    state, _ws_path, eval_data, evaluate_round, active_doc, _mode = ctx
    dimension_token = str(payload["dimension_token"])
    paths = session_binding._eval_paths(
        cycle_id,
        project_root,
        active_doc=active_doc,
        evaluate_round=evaluate_round,
        es_path=session_binding._evaluate_state_path(cycle_id, project_root),
    )
    operations_path = session_binding._operations_path(paths)
    try:
        record = ec.get_operation_record(operations_path, dimension_token)
    except ValueError as exc:
        return ec._failure(ec._CMD_SUBMIT_PROBE_FINDINGS, str(exc))
    if (
        record.get("operation_kind") != "probe"
        or record.get("round_token") != eval_data["round_token"]
    ):
        return ec._failure(
            ec._CMD_SUBMIT_PROBE_FINDINGS,
            "operation_token is not authorized for this probe round",
            dimension_token=dimension_token,
        )

    dimension_id = str(record["dimension_id"])
    policies = ec.parse_handling_policy(eval_data["handling_policy"])
    handling_policy = policies.get(dimension_id)
    if handling_policy is None:
        return ec._failure(
            ec._CMD_SUBMIT_PROBE_FINDINGS,
            f"handling_policy missing dimension: {dimension_id!r}",
        )
    canonical_findings = [
        {
            **finding,
            "handling_mode": review_binding.handling_mode_for_issue(
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
            return ec._success(
                ec._CMD_SUBMIT_PROBE_FINDINGS,
                dimension_token=dimension_token,
                outcome="probed",
                idempotent=True,
                review_path=record.get("review_path", ""),
            )
        return ec._failure(
            ec._CMD_SUBMIT_PROBE_FINDINGS,
            "conflict: different submission for operation_token",
            dimension_token=dimension_token,
        )
    if record.get("phase") in {"prepared", "target-applied", "review-applied"}:
        if record.get("submission_digest") != submission_digest:
            return ec._failure(
                ec._CMD_SUBMIT_PROBE_FINDINGS,
                "conflict: different submission for operation_token",
                dimension_token=dimension_token,
            )
        recovered = operation_recovery._forward_recover_to_committed(
            cycle_id,
            project_root,
            command=ec._CMD_SUBMIT_PROBE_FINDINGS,
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
        corpus = session_binding._load_corpus(cycle_id, project_root)
        total_issues = len(record.get("canonical_findings") or [])

        def _recover_patch(data: dict[str, str]) -> dict[str, str]:
            next_status = "complete" if total_issues == 0 else "probed"
            updated = ec.merge_current_dimension(
                data,
                dimension_id,
                next_status,
                corpus=corpus or None,
            )
            return session_binding._recompute_aggregate_counts(
                ec.patch_issue_count(updated, dimension_id, total=str(total_issues)),
            )

        error = evaluate_context._commit_staged_evaluate_state(
            cycle_id,
            project_root,
            update=_recover_patch,
        )
        if error is not None:
            return ec._failure(
                ec._CMD_SUBMIT_PROBE_FINDINGS,
                f"projection_pending: {error}",
            )
        return ec._success(
            ec._CMD_SUBMIT_PROBE_FINDINGS,
            dimension_token=dimension_token,
            operation_token=dimension_token,
            outcome="probed",
            idempotent=False,
            total_issues=str(total_issues),
            review_path=review_path.resolve().as_posix() if review_path else "",
            findings=record.get("canonical_findings") or [],
        )
    if record.get("phase") != "context-open":
        return ec._failure(
            ec._CMD_SUBMIT_PROBE_FINDINGS,
            f"repair_required: probe operation phase is {record.get('phase')!r}",
        )
    if ec.parse_dimension_status(eval_data["dimension_status"]).get(
        dimension_id,
    ) != "probing":
        return ec._failure(
            ec._CMD_SUBMIT_PROBE_FINDINGS,
            "operation_token does not own a probing dimension",
        )

    expanded = session_binding._expanded_corpus(
        cycle_id,
        state,
        paths,
        evaluate_round,
        project_root=project_root,
    )
    dim_def = session_binding._dimension_def(expanded, dimension_id)
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
        return ec._failure(ec._CMD_SUBMIT_PROBE_FINDINGS, str(exc))
    review_path = review_binding._review_path_for_dim(
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
        record = operation_recovery._advance_phase(operations_path, prepared, "prepared")
    except ValueError as exc:
        return ec._failure(ec._CMD_SUBMIT_PROBE_FINDINGS, str(exc))
    recovered = operation_recovery._forward_recover_to_committed(
        cycle_id,
        project_root,
        command=ec._CMD_SUBMIT_PROBE_FINDINGS,
        operations_path=operations_path,
        record=record,
        paths=paths,
        review_path=review_path,
        evaluate_round=evaluate_round,
    )
    if not recovered.get("ok"):
        return recovered
    record = recovered["record"]

    corpus = session_binding._load_corpus(cycle_id, project_root)
    total_issues = len(canonical_findings)

    def _patch(data: dict[str, str]) -> dict[str, str]:
        next_status = "complete" if total_issues == 0 else "probed"
        updated = ec.merge_current_dimension(
            data,
            dimension_id,
            next_status,
            corpus=corpus,
        )
        return session_binding._recompute_aggregate_counts(
            ec.patch_issue_count(updated, dimension_id, total=str(total_issues)),
        )

    error = evaluate_context._commit_staged_evaluate_state(cycle_id, project_root, update=_patch)
    if error is not None:
        return ec._failure(
            ec._CMD_SUBMIT_PROBE_FINDINGS,
            f"projection_pending: {error}",
        )
    return ec._success(
        ec._CMD_SUBMIT_PROBE_FINDINGS,
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
    ctx = evaluate_context._load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx["command"] = ec._CMD_CHECK_DIMENSION
        ctx["dim"] = dim
        ctx["outcome"] = "incomplete"
        ctx["abandoned"] = False
        return ctx

    state, _ws_path, eval_data, evaluate_round, active_doc, mode = ctx
    if not session_binding._dispatch_dim_allowed(cycle_id, project_root, dim):
        return ec._failure(
            ec._CMD_CHECK_DIMENSION,
            f"invalid dim: {dim!r} (not in corpus for mode {mode!r}).",
            current_state=state["current_state"],
            dim=dim,
            outcome="incomplete",
            abandoned=False,
        )

    eval_status = eval_data.get("eval_status", "")
    if eval_status == "abandoned":
        return ec._success(
            ec._CMD_CHECK_DIMENSION,
            dim=dim,
            outcome="abandoned",
            abandoned=True,
            current_state=state["current_state"],
            eval_status=eval_status,
        )

    corpus = session_binding._load_corpus(cycle_id, project_root)
    dim_map = ec.dimension_status_legacy_map(eval_data, corpus=corpus)
    dim_status = dim_map.get(dim, "pending")
    dim_id = session_binding._canonical_dim(cycle_id, project_root, dim)

    review_path = review_binding._review_path_from_context(
        cycle_id,
        project_root,
        state=state,
        evaluate_round=evaluate_round,
        active_doc=active_doc,
        dim=dim,
    )

    if review_path.exists() and dim_status not in {"probed", "complete"}:
        return ec._failure(
            ec._CMD_CHECK_DIMENSION,
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
        return ec._failure(
            ec._CMD_CHECK_DIMENSION,
            f"{dim} status is {dim_status!r}, expected 'probed' or 'complete'.",
            current_state=state["current_state"],
            dim=dim,
            outcome="incomplete",
            abandoned=False,
            dim_status=dim_status,
        )

    validation_errors = ec.validate_review_file(review_path, phase="probe")
    if validation_errors:
        return ec._failure(
            ec._CMD_CHECK_DIMENSION,
            "; ".join(validation_errors),
            current_state=state["current_state"],
            dim=dim,
            outcome="incomplete",
            abandoned=False,
            review_path=review_path.resolve().as_posix(),
        )

    rows = ec.parse_review_file(review_path)
    for row in rows:
        row["dimension"] = dim

    counts = ec.parse_issue_counts(eval_data.get("issue_counts", "{}"))
    dim_total = counts.get(dim_id, {}).get("total", "0")

    return ec._success(
        ec._CMD_CHECK_DIMENSION,
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
