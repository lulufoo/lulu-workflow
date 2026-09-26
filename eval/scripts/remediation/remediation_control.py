#!/usr/bin/env python3
"""Eval remediation control — unified remediation commands.

Owns begin/cancel/prepare/apply/check/complete for the remediation family.
eval_control.run_eval forwards here. Invoke via eval_entry.py. Not __main__.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import eval_control as ec
import evaluate_context
import operation_recovery
import review_binding
import session_binding

def prepare_remediation_at(*, operations_path: Path, proposal_file: Path) -> dict[str, Any]:
    """Validate and canonicalize a proposal without writing any Eval-owned file."""
    try:
        candidate = json.loads(proposal_file.read_text(encoding='utf-8'))
    except OSError as exc:
        raise ValueError(f'cannot read proposal file: {proposal_file}: {exc}') from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f'invalid remediation proposal JSON: {exc}') from exc
    if not isinstance(candidate, dict):
        raise ValueError('remediation proposal must be an object')
    operation_token = candidate.get('operation_token')
    if not isinstance(operation_token, str) or not operation_token:
        raise ValueError('remediation proposal operation_token must be non-empty')
    operation = ec.get_operation_record(operations_path, operation_token)
    if operation.get('operation_kind') != 'remediation':
        raise ValueError('operation_token is not a remediation operation')
    return ec.prepare_remediation_proposal(operation, candidate)

def _application_outcome(record: dict[str, Any]) -> str | None:
    application = record.get('remediation_application')
    if not isinstance(application, dict):
        return None
    final = application.get('final')
    if not isinstance(final, dict):
        return None
    outcome = final.get('outcome')
    return str(outcome) if outcome is not None else None

def _abandoned_failure(
    command: str,
    state: dict[str, str],
    eval_data: dict[str, str],
) -> dict[str, Any] | None:
    if eval_data.get("eval_status") != "abandoned":
        return None
    return ec._failure(
        command,
        "evaluation was abandoned (eval_status: abandoned).",
        current_state=state["current_state"],
    )


def _committed_abandon_record(operations: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in operations:
        if record.get('operation_kind') == 'remediation' and record.get('phase') == 'committed' and (_application_outcome(record) == 'abandon'):
            return record
    return None

def _project_abandoned_round(cycle_id: str, project_root: Path, *, command: str, eval_data: dict[str, str], record: dict[str, Any], review_path: Path | None, extra_failure: dict[str, Any] | None=None) -> dict[str, Any] | None:
    """Rebuild abandoned/done from Review + committed abandon. None on success."""
    extra = extra_failure or {}
    dimension_id = str(record['dimension_id'])
    rows: list[dict[str, str]] = []
    if review_path is not None and review_path.is_file():
        try:
            rows = ec.parse_review_file(review_path, expected_dimension_id=dimension_id, expected_round_token=str(eval_data['round_token']))
        except ValueError as exc:
            return ec._failure(command, str(exc), **extra)

    def _project(data: dict[str, str]) -> dict[str, str]:
        updated = dict(data)
        updated['eval_status'] = 'abandoned'
        updated['eval_phase'] = 'done'
        if rows:
            updated = ec.patch_issue_count(updated, dimension_id, total=str(len(rows)), resolved=str(ec.count_resolved(rows)))
            updated = session_binding._recompute_aggregate_counts(updated)
        return updated
    error = evaluate_context._commit_staged_evaluate_state(cycle_id, project_root, update=_project)
    if error is not None:
        return ec._failure(command, f'projection_pending: {error}', **extra)
    eval_data['eval_status'] = 'abandoned'
    eval_data['eval_phase'] = 'done'
    return None

def _sync_committed_abandon_projection(cycle_id: str, project_root: Path, *, command: str, state: dict[str, str], eval_data: dict[str, str], evaluate_round: int, active_doc: int, paths: dict[str, str], refuse_new_context: bool=False, extra_failure: dict[str, Any] | None=None) -> dict[str, Any] | None:
    """Rebuild abandon projection on entry. Optionally refuse a new context."""
    extra = extra_failure or {}
    abandon = _committed_abandon_record(session_binding._operations_for_round(paths, eval_data['round_token']))
    if abandon is None:
        return None
    try:
        review_path = review_binding._review_path_from_context(cycle_id, project_root, state=state, evaluate_round=evaluate_round, active_doc=active_doc, dim=str(abandon['dimension_id']))
    except (OSError, ValueError):
        review_path = None
    blocked = _project_abandoned_round(cycle_id, project_root, command=command, eval_data=eval_data, record=abandon, review_path=review_path, extra_failure=extra)
    if blocked is not None:
        return blocked
    if refuse_new_context:
        failure = _abandoned_failure(command, state, eval_data)
        if failure is not None:
            failure.update(extra)
        return failure
    return None

def _remediation_command_context(command: str, cycle_id: str, project_root: Path) -> tuple[dict[str, str], dict[str, str], int, int, dict[str, str]] | dict[str, Any]:
    """Load common full-remediation command state and paths."""
    ctx = evaluate_context._load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx['command'] = command
        return ctx
    (state, _ws_path, eval_data, evaluate_round, active_doc, _mode) = ctx
    if eval_data.get('eval_capability') != 'full-remediation':
        return ec._failure(command, 'probe-only round rejects remediation commands')
    paths = session_binding._eval_paths(cycle_id, project_root, active_doc=active_doc, evaluate_round=evaluate_round, es_path=session_binding._evaluate_state_path(cycle_id, project_root))
    synced = _sync_committed_abandon_projection(cycle_id, project_root, command=command, state=state, eval_data=eval_data, evaluate_round=evaluate_round, active_doc=active_doc, paths=paths, refuse_new_context=command == ec._CMD_BEGIN_DIMENSION_REMEDIATION)
    if synced is not None:
        return synced
    return (state, eval_data, evaluate_round, active_doc, paths)

def begin_remediation(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Enter unified remediation after every Probe operation is committed."""
    loaded = _remediation_command_context(ec._CMD_BEGIN_REMEDIATION, cycle_id, project_root)
    if isinstance(loaded, dict):
        return loaded
    (state, eval_data, evaluate_round, active_doc, paths) = loaded
    phase = eval_data.get('eval_phase')
    if phase not in {'probe', 'remediation'}:
        return ec._failure(ec._CMD_BEGIN_REMEDIATION, f"eval_phase is {phase!r}, expected 'probe' or 'remediation'")
    dimensions = ec.parse_dimension_status(eval_data['dimension_status'])
    active_dimensions = {dim_id: status for (dim_id, status) in dimensions.items() if status != 'skipped'}
    if phase == 'probe' and any((status not in {'probed', 'complete'} for status in active_dimensions.values())):
        return ec._failure(ec._CMD_BEGIN_REMEDIATION, 'not all dimensions are probed or complete')
    operations = session_binding._operations_for_round(paths, eval_data['round_token'])
    if any((record.get('operation_kind') == 'probe' and record.get('phase') != 'committed' for record in operations)):
        return ec._failure(ec._CMD_BEGIN_REMEDIATION, 'open probe operation prevents remediation')
    committed_probe_dimensions = {str(record.get('dimension_id')) for record in operations if record.get('operation_kind') == 'probe' and record.get('phase') == 'committed'}
    if not set(active_dimensions) <= committed_probe_dimensions:
        return ec._failure(ec._CMD_BEGIN_REMEDIATION, 'missing committed probe operation for one or more dimensions')
    probe_by_dimension = {str(record.get('dimension_id')): record for record in operations if record.get('operation_kind') == 'probe' and record.get('phase') == 'committed'}
    for dimension_id in active_dimensions:
        review_path = review_binding._review_path_from_context(cycle_id, project_root, state=state, evaluate_round=evaluate_round, active_doc=active_doc, dim=dimension_id)
        if not review_path.is_file():
            return ec._failure(ec._CMD_BEGIN_REMEDIATION, f'ReviewFile missing for dimension {dimension_id!r}')
        try:
            rows = ec.parse_review_file(review_path, expected_dimension_id=dimension_id, expected_round_token=eval_data['round_token'])
            review_binding.validate_review_against_probe_record(rows, probe_by_dimension[dimension_id])
            if any((row.get('status') == 'resolved' for row in rows)):
                review_binding.validate_review_completion(rows=rows, dimension_id=dimension_id, remediation_records=operations, review_digest=hashlib.sha256(review_path.read_bytes()).hexdigest())
        except ValueError as exc:
            return ec._failure(ec._CMD_BEGIN_REMEDIATION, str(exc))
    if phase == 'probe':
        error = evaluate_context._commit_staged_evaluate_state(cycle_id, project_root, patch={'eval_phase': 'remediation'})
        if error is not None:
            return ec._failure(ec._CMD_BEGIN_REMEDIATION, error)
    dispatch = [dimension_id for (dimension_id, status) in dimensions.items() if status == 'probed']
    return ec._success(ec._CMD_BEGIN_REMEDIATION, skip=not dispatch, dispatch=dispatch, dimension_dispatch=eval_data.get('dimension_dispatch', 'parallel'), current_state=state['current_state'], eval_phase='remediation')

def begin_dimension_remediation(cycle_id: str, project_root: Path, *, dim: str) -> dict[str, Any]:
    """Create or resume one all-pending-Issue remediation context."""
    loaded = _remediation_command_context(ec._CMD_BEGIN_DIMENSION_REMEDIATION, cycle_id, project_root)
    if isinstance(loaded, dict):
        loaded['dim'] = dim
        return loaded
    (state, eval_data, evaluate_round, active_doc, paths) = loaded
    blocked = _sync_committed_abandon_projection(cycle_id, project_root, command=ec._CMD_BEGIN_DIMENSION_REMEDIATION, state=state, eval_data=eval_data, evaluate_round=evaluate_round, active_doc=active_doc, paths=paths, refuse_new_context=True, extra_failure={'dim': dim})
    if blocked is not None:
        return blocked
    if eval_data.get('eval_phase') != 'remediation':
        return ec._failure(ec._CMD_BEGIN_DIMENSION_REMEDIATION, "eval_phase must be 'remediation'", dim=dim)
    try:
        dimension_id = session_binding._canonical_dim(cycle_id, project_root, dim)
    except ValueError as exc:
        return ec._failure(ec._CMD_BEGIN_DIMENSION_REMEDIATION, str(exc), dim=dim)
    dimension_status = ec.parse_dimension_status(eval_data['dimension_status'])
    if dimension_status.get(dimension_id) not in {'probed', 'remediating', 'complete'}:
        return ec._failure(ec._CMD_BEGIN_DIMENSION_REMEDIATION, f'dimension is not probed: {dimension_id!r}', dim=dim)
    review_path = review_binding._review_path_from_context(cycle_id, project_root, state=state, evaluate_round=evaluate_round, active_doc=active_doc, dim=dimension_id)
    try:
        rows = ec.parse_review_file(review_path, expected_dimension_id=dimension_id, expected_round_token=eval_data['round_token'])
    except ValueError as exc:
        return ec._failure(ec._CMD_BEGIN_DIMENSION_REMEDIATION, str(exc), dim=dim)
    operations = session_binding._operations_for_round(paths, eval_data['round_token'])
    probe_record = next((record for record in operations if record.get('operation_kind') == 'probe' and record.get('phase') == 'committed' and (record.get('dimension_id') == dimension_id)), None)
    try:
        if probe_record is None:
            raise ValueError('missing committed probe operation')
        review_binding.validate_review_against_probe_record(rows, probe_record)
    except ValueError as exc:
        return ec._failure(ec._CMD_BEGIN_DIMENSION_REMEDIATION, str(exc), dim=dim)
    pending = [row for row in rows if row.get('status', '').lower() == 'pending']
    if not pending:
        try:
            review_binding.validate_review_completion(rows=rows, dimension_id=dimension_id, remediation_records=operations, review_digest=hashlib.sha256(review_path.read_bytes()).hexdigest())
        except ValueError as exc:
            return ec._failure(ec._CMD_BEGIN_DIMENSION_REMEDIATION, str(exc), dim=dim)
        corpus = session_binding._load_corpus(cycle_id, project_root)

        def _complete_zero(data: dict[str, str]) -> dict[str, str]:
            updated = ec.merge_current_dimension(data, dimension_id, 'complete', corpus=corpus)
            return session_binding._recompute_aggregate_counts(ec.patch_issue_count(updated, dimension_id, total=str(len(rows)), resolved=str(ec.count_resolved(rows))))
        error = evaluate_context._commit_staged_evaluate_state(cycle_id, project_root, update=_complete_zero)
        if error is not None:
            return ec._failure(ec._CMD_BEGIN_DIMENSION_REMEDIATION, error, dim=dim)
        return ec._success(ec._CMD_BEGIN_DIMENSION_REMEDIATION, dim=dim, skip=True)
    if dimension_status.get(dimension_id) == 'complete':
        return ec._failure(ec._CMD_BEGIN_DIMENSION_REMEDIATION, 'complete dimension has pending Review findings', dim=dim)
    required_issue_ids = [row['id'] for row in pending]
    handling_modes = {row['id']: row['handling_mode'].lower() for row in pending}
    try:
        allowed_decisions = {row['id']: review_binding.allowed_decisions_for_issue(row['root_cause'], handling_modes[row['id']]) for row in pending}
        expanded = session_binding._expanded_corpus(cycle_id, state, paths, evaluate_round, project_root=project_root)
        dim_def = session_binding._dimension_def(expanded, dimension_id)
        operation_ctx = ec.issue_remediation_context(operations_path=session_binding._operations_path(paths), write_staging_dir=Path(paths.get('write_staging_dir') or paths['evaluate_dir']), target_path=Path(str(dim_def['eval_target']['path'])), review_path=review_path, round_token=eval_data['round_token'], dimension_id=dimension_id, method=dict(dim_def['method']), sots=[dict(sot) for sot in dim_def['sots']], required_issue_ids=required_issue_ids, handling_modes_by_issue=handling_modes, allowed_decisions_by_issue=allowed_decisions)
    except (OSError, ValueError) as exc:
        return ec._failure(ec._CMD_BEGIN_DIMENSION_REMEDIATION, str(exc), dim=dim)
    corpus = session_binding._load_corpus(cycle_id, project_root)
    error = evaluate_context._commit_staged_evaluate_state(cycle_id, project_root, update=lambda data: ec.merge_current_dimension(data, dimension_id, 'remediating', corpus=corpus))
    if error is not None:
        return ec._failure(ec._CMD_BEGIN_DIMENSION_REMEDIATION, f'projection_pending: {error}', dim=dim)
    return ec._success(ec._CMD_BEGIN_DIMENSION_REMEDIATION, dim=dim, skip=False, operation_ctx=operation_ctx, dispatch_input=_format_remediation_dispatch_input(operation_ctx, pending))

def cancel_remediation(cycle_id: str, project_root: Path, *, operation_token: str) -> dict[str, Any]:
    """Cancel only a context-open remediation and release its persisted lease."""
    loaded = _remediation_command_context(ec._CMD_CANCEL_REMEDIATION, cycle_id, project_root)
    if isinstance(loaded, dict):
        return loaded
    (_state, eval_data, _evaluate_round, _active_doc, paths) = loaded
    try:
        current = ec.get_operation_record(session_binding._operations_path(paths), operation_token)
        if current.get('operation_kind') != 'remediation' or current.get('round_token') != eval_data['round_token']:
            raise ValueError('operation_token is not owned by this remediation round')
        cancelled = ec.cancel_operation_record(session_binding._operations_path(paths), operation_token)
    except ValueError as exc:
        return ec._failure(ec._CMD_CANCEL_REMEDIATION, str(exc))
    if cancelled.get('phase') == 'cancelled':
        dimension_id = str(cancelled['dimension_id'])
        corpus = session_binding._load_corpus(cycle_id, project_root)
        error = evaluate_context._commit_staged_evaluate_state(cycle_id, project_root, update=lambda data: ec.merge_current_dimension(data, dimension_id, 'probed', corpus=corpus))
        if error is not None:
            return ec._failure(ec._CMD_CANCEL_REMEDIATION, f'projection_pending: {error}')
    return ec._success(ec._CMD_CANCEL_REMEDIATION, operation_token=operation_token, phase=cancelled['phase'], dimension_status='probed' if cancelled['phase'] == 'cancelled' else None)

def prepare_remediation(cycle_id: str, project_root: Path, *, proposal_file: Path) -> dict[str, Any]:
    """Expose the read-only proposal validator through the Control API."""
    loaded = _remediation_command_context(ec._CMD_PREPARE_REMEDIATION, cycle_id, project_root)
    if isinstance(loaded, dict):
        return loaded
    (_state, eval_data, _evaluate_round, _active_doc, paths) = loaded
    if eval_data.get('eval_phase') != 'remediation':
        return ec._failure(ec._CMD_PREPARE_REMEDIATION, 'eval_phase must be remediation')
    try:
        prepared = prepare_remediation_at(operations_path=session_binding._operations_path(paths), proposal_file=proposal_file)
    except ValueError as exc:
        return ec._failure(ec._CMD_PREPARE_REMEDIATION, str(exc))
    return ec._success(ec._CMD_PREPARE_REMEDIATION, **prepared)

def _project_after_remediation(cycle_id: str, project_root: Path, *, record: dict[str, Any], review_path: Path, eval_data: dict[str, str], idempotent: bool) -> dict[str, Any]:
    application = record.get('remediation_application')
    if not isinstance(application, dict):
        return ec._failure(ec._CMD_APPLY_REMEDIATION, 'repair_required: committed remediation missing application')
    outcome = str(application.get('final', {}).get('outcome') or 'apply')
    dimension_id = str(record['dimension_id'])
    try:
        rows = ec.parse_review_file(review_path, expected_dimension_id=dimension_id, expected_round_token=str(eval_data['round_token']))
    except ValueError as exc:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, str(exc))
    pending = [row for row in rows if row.get('status') == 'pending']
    corpus = session_binding._load_corpus(cycle_id, project_root) or None

    def _project(data: dict[str, str]) -> dict[str, str]:
        updated = dict(data)
        if outcome == 'abandon':
            updated['eval_status'] = 'abandoned'
            updated['eval_phase'] = 'done'
        else:
            next_status = 'complete' if not pending else 'remediating'
            updated = ec.merge_current_dimension(updated, dimension_id, next_status, corpus=corpus)
        updated = ec.patch_issue_count(updated, dimension_id, total=str(len(rows)), resolved=str(ec.count_resolved(rows)))
        return session_binding._recompute_aggregate_counts(updated)
    error = evaluate_context._commit_staged_evaluate_state(cycle_id, project_root, update=_project)
    if error is not None:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, f'projection_pending: {error}')
    return ec._success(ec._CMD_APPLY_REMEDIATION, operation_token=record['operation_token'], outcome=outcome, target_effect=record.get('target_effect'), idempotent=idempotent, eval_status='abandoned' if outcome == 'abandon' else eval_data.get('eval_status'))

def apply_remediation(cycle_id: str, project_root: Path, *, application_file: Path) -> dict[str, Any]:
    """Validate a RemediationApplication and commit the unified transaction."""
    loaded = _remediation_command_context(ec._CMD_APPLY_REMEDIATION, cycle_id, project_root)
    if isinstance(loaded, dict):
        return loaded
    (_state, eval_data, evaluate_round, active_doc, paths) = loaded
    try:
        application = json.loads(application_file.read_text(encoding='utf-8'))
    except OSError as exc:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, f'cannot read application file: {application_file}: {exc}')
    except json.JSONDecodeError as exc:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, f'invalid remediation application JSON: {exc}')
    if not isinstance(application, dict) or not isinstance(application.get('proposal'), dict):
        return ec._failure(ec._CMD_APPLY_REMEDIATION, 'application must embed a proposal')
    operation_token = application['proposal'].get('operation_token')
    if not isinstance(operation_token, str) or not operation_token:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, 'application proposal.operation_token must be non-empty')
    operations_path = session_binding._operations_path(paths)
    try:
        record = ec.get_operation_record(operations_path, operation_token)
    except ValueError as exc:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, str(exc))
    if record.get('operation_kind') != 'remediation' or record.get('round_token') != eval_data['round_token']:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, 'operation_token is not owned by this remediation round')
    review_path = review_binding._review_path_from_context(cycle_id, project_root, state=_state, evaluate_round=evaluate_round, active_doc=active_doc, dim=str(record['dimension_id']))
    phase = record.get('phase')
    if phase == 'cancelled':
        return ec._failure(ec._CMD_APPLY_REMEDIATION, 'cancelled operation cannot be applied')
    if phase in {'prepared', 'target-applied', 'review-applied', 'committed'}:
        digest = ec.application_submission_digest(record, ec.canonicalize_remediation_application(record, application))
        if digest != record.get('submission_digest'):
            return ec._failure(ec._CMD_APPLY_REMEDIATION, 'conflict: different submission for operation_token')
        if phase == 'committed':
            return _project_after_remediation(cycle_id, project_root, record=record, review_path=review_path, eval_data=eval_data, idempotent=True)
        recovered = operation_recovery._forward_recover_to_committed(cycle_id, project_root, command=ec._CMD_APPLY_REMEDIATION, operations_path=operations_path, record=record, paths=paths, review_path=review_path, evaluate_round=evaluate_round)
        if not recovered.get('ok'):
            return recovered
        return _project_after_remediation(cycle_id, project_root, record=recovered['record'], review_path=review_path, eval_data=eval_data, idempotent=False)
    if eval_data.get('eval_phase') != 'remediation':
        return ec._failure(ec._CMD_APPLY_REMEDIATION, 'eval_phase must be remediation')
    if phase != 'context-open':
        return ec._failure(ec._CMD_APPLY_REMEDIATION, f'repair_required: unknown operation phase {phase!r}')
    errors = ec.validate_remediation_application(record, application)
    if errors:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, f"remediation application invalid: {'; '.join(errors)}")
    try:
        target_path = operation_recovery._target_path_from_record(record)
        live_target = operation_recovery._live_target_digest(cycle_id, project_root, target_path)
    except (OSError, ValueError) as exc:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, str(exc))
    if live_target != record['target_base_digest']:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, 'stale target: live digest does not match operation target_base_digest')
    if not review_path.is_file():
        return ec._failure(ec._CMD_APPLY_REMEDIATION, 'stale review: ReviewFile missing')
    before_content = review_path.read_text(encoding='utf-8')
    if operation_recovery._content_digest(before_content) != record['review_base_digest']:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, 'stale review: live digest does not match operation review_base_digest')
    canonical = ec.canonicalize_remediation_application(record, application)
    final = canonical['final']
    outcome = str(final['outcome'])
    updates = {str(entry['issue_id']): ('resolved', str(entry['decision']), str(entry['resolution'])) for entry in final.get('resolutions', []) if isinstance(entry, dict)}
    after_content = operation_recovery._render_review_after(before_content, updates)
    review_errors = ec.validate_review_content(after_content, phase='remediation')
    if review_errors:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, f"generated review invalid: {'; '.join(review_errors)}")
    target_effect = 'none'
    target_after_digest = str(record['target_base_digest'])
    staged_path: str | None = None
    mutation = final.get('mutation')
    if outcome == 'apply' and mutation is not None:
        snapshot_path = record.get('snapshot_path')
        if not isinstance(snapshot_path, str) or not snapshot_path:
            return ec._failure(ec._CMD_APPLY_REMEDIATION, 'operation snapshot_path is missing')
        try:
            after_target = ec.apply_unified_diff(Path(snapshot_path).read_text(encoding='utf-8'), str(mutation['unified_diff']))
        except ValueError as exc:
            return ec._failure(ec._CMD_APPLY_REMEDIATION, str(exc))
        if after_target == Path(snapshot_path).read_text(encoding='utf-8'):
            return ec._failure(ec._CMD_APPLY_REMEDIATION, 'empty or no-op unified_diff is rejected')
        target_after_digest = operation_recovery._content_digest(after_target)
        if target_after_digest == record['target_base_digest']:
            return ec._failure(ec._CMD_APPLY_REMEDIATION, 'empty or no-op unified_diff is rejected')
        staged = Path(paths['write_staging_dir']) / f'{operation_token}-target.staged'
        ec._atomic_write_text(staged, after_target)
        staged_path = staged.as_posix()
        target_effect = 'mutation'
    prepared = {**record, 'phase': 'prepared', 'submission_digest': ec.application_submission_digest(record, canonical), 'target_effect': target_effect, 'target_after_digest': target_after_digest, 'review_after_digest': operation_recovery._content_digest(after_content), 'canonical_findings': None, 'remediation_application': canonical, 'review_before_content': before_content, 'review_after_content': after_content, 'target_staged_path': staged_path, 'review_path': review_path.resolve().as_posix()}
    try:
        record = operation_recovery._advance_phase(operations_path, prepared, 'prepared')
    except ValueError as exc:
        return ec._failure(ec._CMD_APPLY_REMEDIATION, str(exc))
    recovered = operation_recovery._forward_recover_to_committed(cycle_id, project_root, command=ec._CMD_APPLY_REMEDIATION, operations_path=operations_path, record=record, paths=paths, review_path=review_path, evaluate_round=evaluate_round)
    if not recovered.get('ok'):
        return recovered
    return _project_after_remediation(cycle_id, project_root, record=recovered['record'], review_path=review_path, eval_data=eval_data, idempotent=False)

def restore_eval_target(cycle_id: str, project_root: Path, *, snapshot_path: Path, expected_current_digest: str, target_path: Path) -> dict[str, Any]:
    """CAS restore of one EvalTarget; refuses when live digest drifted."""
    del target_path
    paths = session_binding._paths_from_handoff() or {}
    result = ec._adapter().restore_eval_target(cycle_id, project_root, snapshot_path=snapshot_path, expected_current_digest=expected_current_digest, lease_id=str(paths.get('lease_id', '')))
    if not result.get('ok'):
        return ec._failure('restore-eval-target', str(result.get('error') or 'restore_eval_target failed'))
    return ec._success('restore-eval-target')

def check_dimension_remediation(cycle_id: str, project_root: Path, *, dim: str) -> dict[str, Any]:
    """Derive one Dimension projection from Review v3 and v4 operations."""
    loaded = _remediation_command_context(ec._CMD_CHECK_DIMENSION_REMEDIATION, cycle_id, project_root)
    if isinstance(loaded, dict):
        loaded['dim'] = dim
        return loaded
    (state, eval_data, evaluate_round, active_doc, paths) = loaded
    try:
        dimension_id = session_binding._canonical_dim(cycle_id, project_root, dim)
        review_path = review_binding._review_path_from_context(cycle_id, project_root, state=state, evaluate_round=evaluate_round, active_doc=active_doc, dim=dimension_id)
        rows = ec.parse_review_file(review_path, expected_dimension_id=dimension_id, expected_round_token=eval_data['round_token'])
    except ValueError as exc:
        return ec._failure(ec._CMD_CHECK_DIMENSION_REMEDIATION, str(exc), dim=dim)
    pending = [row for row in rows if row.get('status') == 'pending']
    records = [record for record in session_binding._operations_for_round(paths, eval_data['round_token']) if record.get('operation_kind') == 'remediation' and record.get('dimension_id') == dimension_id]
    probe_record = next((record for record in session_binding._operations_for_round(paths, eval_data['round_token']) if record.get('operation_kind') == 'probe' and record.get('phase') == 'committed' and (record.get('dimension_id') == dimension_id)), None)
    try:
        if probe_record is None:
            raise ValueError('missing committed probe operation')
        review_binding.validate_review_against_probe_record(rows, probe_record)
    except ValueError as exc:
        return ec._failure(ec._CMD_CHECK_DIMENSION_REMEDIATION, str(exc), dim=dim)
    latest = records[-1] if records else None
    if not pending:
        try:
            review_binding.validate_review_completion(rows=rows, dimension_id=dimension_id, remediation_records=records, review_digest=hashlib.sha256(review_path.read_bytes()).hexdigest())
        except ValueError as exc:
            return ec._failure(ec._CMD_CHECK_DIMENSION_REMEDIATION, str(exc), dim=dim)
        projected = 'complete'
    elif latest is None or latest.get('phase') == 'cancelled':
        projected = 'probed'
    elif latest.get('phase') == 'committed':
        if _application_outcome(latest) == 'abandon':
            blocked = _project_abandoned_round(cycle_id, project_root, command=ec._CMD_CHECK_DIMENSION_REMEDIATION, eval_data=eval_data, record=latest, review_path=review_path, extra_failure={'dim': dim})
            if blocked is not None:
                return blocked
            return ec._success(ec._CMD_CHECK_DIMENSION_REMEDIATION, dim=dim, dimension_status=ec.parse_dimension_status(eval_data['dimension_status']).get(dimension_id), pending_issue_ids=[row['id'] for row in pending], operation_phase=latest.get('phase'), eval_status='abandoned')
        return ec._failure(ec._CMD_CHECK_DIMENSION_REMEDIATION, 'repair_required: committed operation left pending issues', dim=dim)
    else:
        projected = 'remediating'
    corpus = session_binding._load_corpus(cycle_id, project_root)

    def _project(data: dict[str, str]) -> dict[str, str]:
        updated = ec.merge_current_dimension(data, dimension_id, projected, corpus=corpus)
        updated = ec.patch_issue_count(updated, dimension_id, total=str(len(rows)), resolved=str(ec.count_resolved(rows)))
        return session_binding._recompute_aggregate_counts(updated)
    error = evaluate_context._commit_staged_evaluate_state(cycle_id, project_root, update=_project)
    if error is not None:
        return ec._failure(ec._CMD_CHECK_DIMENSION_REMEDIATION, error, dim=dim)
    return ec._success(ec._CMD_CHECK_DIMENSION_REMEDIATION, dim=dim, dimension_status=projected, pending_issue_ids=[row['id'] for row in pending], operation_phase=latest.get('phase') if latest else None)

def remediation_complete(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Finish a full-remediation round only from Review and operation facts."""
    loaded = _remediation_command_context(ec._CMD_REMEDIATION_COMPLETE, cycle_id, project_root)
    if isinstance(loaded, dict):
        return loaded
    (state, eval_data, evaluate_round, active_doc, paths) = loaded
    if eval_data.get('eval_phase') != 'remediation':
        return ec._failure(ec._CMD_REMEDIATION_COMPLETE, 'eval_phase must be remediation')
    status_by_dim = ec.parse_dimension_status(eval_data['dimension_status'])
    dimensions = [dimension_id for dimension_id in session_binding._dispatch_canonical(cycle_id, project_root) if status_by_dim.get(dimension_id) != 'skipped']
    operations = session_binding._operations_for_round(paths, eval_data['round_token'])
    probe_by_dimension = {str(record.get('dimension_id')): record for record in operations if record.get('operation_kind') == 'probe' and record.get('phase') == 'committed'}
    rows_by_dimension: dict[str, list[dict[str, str]]] = {}
    for dimension_id in dimensions:
        try:
            review_path = review_binding._review_path_from_context(cycle_id, project_root, state=state, evaluate_round=evaluate_round, active_doc=active_doc, dim=dimension_id)
            rows = ec.parse_review_file(review_path, expected_dimension_id=dimension_id, expected_round_token=eval_data['round_token'])
            if dimension_id not in probe_by_dimension:
                raise ValueError('missing committed probe operation')
            review_binding.validate_review_against_probe_record(rows, probe_by_dimension[dimension_id])
            review_binding.validate_review_completion(rows=rows, dimension_id=dimension_id, remediation_records=operations, review_digest=hashlib.sha256(review_path.read_bytes()).hexdigest())
            rows_by_dimension[dimension_id] = rows
        except ValueError as exc:
            return ec._failure(ec._CMD_REMEDIATION_COMPLETE, str(exc))
    pending_ids = [row['id'] for rows in rows_by_dimension.values() for row in rows if row.get('status') == 'pending']
    if pending_ids:
        return ec._failure(ec._CMD_REMEDIATION_COMPLETE, f'pending findings remain: {pending_ids!r}')
    if any((record.get('operation_kind') == 'remediation' and record.get('phase') not in {'committed', 'cancelled'} for record in operations)):
        return ec._failure(ec._CMD_REMEDIATION_COMPLETE, 'open remediation operation remains')
    corpus = session_binding._load_corpus(cycle_id, project_root)

    def _finish(data: dict[str, str]) -> dict[str, str]:
        updated = dict(data)
        for (dimension_id, rows) in rows_by_dimension.items():
            updated = ec.merge_current_dimension(updated, dimension_id, 'complete', corpus=corpus)
            updated = ec.patch_issue_count(updated, dimension_id, total=str(len(rows)), resolved=str(ec.count_resolved(rows)))
        updated = session_binding._recompute_aggregate_counts(updated)
        updated['eval_phase'] = 'done'
        updated['eval_status'] = 'done'
        return updated
    error = evaluate_context._commit_staged_evaluate_state(cycle_id, project_root, update=_finish)
    if error is not None:
        return ec._failure(ec._CMD_REMEDIATION_COMPLETE, error)
    return ec._success(ec._CMD_REMEDIATION_COMPLETE, eval_phase='done', eval_status='done')

def _format_remediation_dispatch_input(operation_ctx: dict[str, Any], pending_issues: list[dict[str, str]]) -> str:
    lines = [f"ROUND_TOKEN: {operation_ctx['round_token']}", f"OPERATION_TOKEN: {operation_ctx['operation_token']}", f"DIMENSION_ID: {operation_ctx['dimension_id']}", f"OPERATION_KIND: {operation_ctx['operation_kind']}", f"TARGET_BASE_DIGEST: {operation_ctx['target_base_digest']}", f"REVIEW_BASE_DIGEST: {operation_ctx['review_base_digest']}", f"ALLOWED_SUBMISSION: {operation_ctx['allowed_submission']}", 'RESOLVED_METHOD: ' + json.dumps(operation_ctx['resolved_method'], ensure_ascii=False), 'RESOLVED_SOTS: ' + json.dumps(operation_ctx['resolved_sots'], ensure_ascii=False), 'PENDING_ISSUES: ' + json.dumps(pending_issues, ensure_ascii=False), 'REQUIRED_ISSUE_IDS: ' + json.dumps(operation_ctx['required_issue_ids'], ensure_ascii=False), 'HANDLING_MODES_BY_ISSUE: ' + json.dumps(operation_ctx['handling_modes_by_issue'], ensure_ascii=False), 'ALLOWED_DECISIONS_BY_ISSUE: ' + json.dumps(operation_ctx['allowed_decisions_by_issue'], ensure_ascii=False)]
    return '\n'.join(lines)
