#!/usr/bin/env python3
"""Eval round control — admit, start, and complete one evaluate round.

Owns init-round, begin-eval-round, and complete-probe-only.
eval_control.run_eval forwards here. Invoke via eval_entry.py. Not __main__.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import eval_control as ec

def build_eval_loop_payload(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Build eval loop context (requires Working + focus evaluating + evaluate-state)."""
    ctx = ec._load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx['command'] = ec._CMD_BEGIN_EVAL_ROUND
        return ctx
    (state, _ws_path, eval_data, evaluate_round, active_doc, mode) = ctx
    es_path = ec._evaluate_state_path(cycle_id, project_root)
    paths = ec._eval_paths(cycle_id, project_root, active_doc=active_doc, evaluate_round=evaluate_round, es_path=es_path)
    return ec._success(ec._CMD_BEGIN_EVAL_ROUND, current_state=state['current_state'], mode=mode, dispatch=ec.dispatch_list(cycle_id, project_root), corpus_ref=eval_data.get('corpus_ref', ''), dimension_dispatch=eval_data.get('dimension_dispatch', 'parallel'), evaluate_round=evaluate_round, M=evaluate_round, active_doc=active_doc, N=active_doc, cycle_type=ec._adapter().detect_cycle_type(cycle_id), upstream_baseline_ref=ec._upstream_baseline_ref(cycle_id, project_root), project_root=project_root.resolve().as_posix(), paths=paths)

def _start_next_eval_round(cycle_id: str, project_root: Path, *, state: dict[str, str], ws_path: Path, mode: str) -> dict[str, Any]:
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
    raw_state = ec.parse_frontmatter_fields(es_path.read_text(encoding='utf-8'))
    if ec.is_v8_state(raw_state):
        return None
    return f"incompatible_round: evaluate-state version {raw_state.get('version')!r} is not supported (expected '8')"

def _require_admission_protocol() -> str | None:
    adapter = ec._adapter()
    missing = [name for name in ('eval_admission_context', 'prepare_eval_admission', 'abort_eval_admission') if not callable(getattr(adapter, name, None))]
    if missing:
        return 'adapter missing admission protocol: ' + ', '.join(missing)
    return None

def _admit_eval_round(cycle_id: str, project_root: Path) -> dict[str, Any] | None:
    """Run two-phase admission. Return a failure payload, or None on success."""
    protocol_error = _require_admission_protocol()
    if protocol_error:
        return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, protocol_error)
    adapter = ec._adapter()
    try:
        ctx = adapter.eval_admission_context(cycle_id, project_root)
    except (OSError, ValueError) as exc:
        return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, str(exc))
    es_path = adapter.resolve_evaluate_state_path(cycle_id, project_root)
    evaluate_dir = Path(adapter.eval_paths(cycle_id, project_root, active_doc=adapter.session_context(cycle_id, project_root).active_doc, evaluate_round=ctx.candidate_round, es_path=es_path)['evaluate_dir'])
    try:
        recovery = ec.recover_admission(ctx, evaluate_state_path=es_path, evaluate_dir=evaluate_dir, focus_phase=ec._focus_phase(cycle_id, project_root))
    except ValueError as exc:
        return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, str(exc))
    if recovery['action'] == 'committed':
        try:
            ec._refresh_handoff(cycle_id, project_root, require_evaluating=True)
        except ValueError as exc:
            return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, str(exc))
        return None
    token = ''
    try:
        journal = ec.load_journal(ctx.admission_root)
        if journal and str(journal.get('status')) in {'prepared', 'transitioned'} and str(journal.get('snapshot_digest') or ''):
            token = str(journal['token'])
            digest = str(journal['snapshot_digest'])
            prepared = {'ok': True, 'token': token, 'snapshot_digest': digest, 'snapshot_ref': ec.SNAPSHOT_REF, 'skip_reasons': dict(journal.get('skip_reasons') or {}), 'corpus': ec.load_prepared_admission_corpus(ctx.admission_root, token=token, evaluate_dir=evaluate_dir, expected_digest=digest)}
        else:
            prepared = adapter.prepare_eval_admission(cycle_id, project_root)
            if not prepared.get('ok'):
                return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, str(prepared.get('error') or 'prepare_eval_admission failed'))
            token = str(prepared['token'])
        entered = False
        if ec._focus_phase(cycle_id, project_root) != ec._EXPECTED_FOCUS_PHASE:
            entry = adapter.enter_evaluating(cycle_id, project_root, admission_token=token)
            if not entry.get('ok'):
                adapter.abort_eval_admission(cycle_id, project_root, token=token)
                return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, str(entry.get('error') or (entry.get('resume') or {}).get('action') or 'cannot enter evaluating'), current_state=entry.get('current_state', ''))
            entered = True
        post_ctx = adapter.eval_admission_context(cycle_id, project_root)
        if post_ctx.target_digest != ctx.target_digest:
            raise ValueError('admission target digest drifted after prepare')
        if not entered:
            ec.mark_transitioned(ctx.admission_root, token=token, provider_state_fingerprint=post_ctx.provider_state_fingerprint)
        handoff = ec._refresh_handoff(cycle_id, project_root, require_evaluating=True)
        from eval_adapter_config import validate_adapter_protocol
        adapter_capability = ''
        for name in ('EVAL_CAPABILITY', '_EVAL_CAPABILITY'):
            adapter_capability = str(getattr(adapter, name, '') or '').strip()
            if adapter_capability in {'full-remediation', 'probe-only'}:
                break
        validate_adapter_protocol(adapter, eval_capability=adapter_capability or ec._eval_capability(), handoff=handoff)
        context = handoff['context']
        journal = ec.load_journal(ctx.admission_root)
        if journal is None:
            raise ValueError('admission journal missing after transition')
        if str(context.get('session_key')) != str(journal.get('session_key')):
            raise ValueError('handoff session_key does not match admission journal')
        if int(context.get('evaluate_round') or 0) != int(journal.get('candidate_round') or 0):
            raise ValueError('handoff evaluate_round does not match admission journal')
        post_handoff = adapter.eval_admission_context(cycle_id, project_root)
        if post_handoff.target_digest != str(journal.get('target_digest') or ''):
            raise ValueError('handoff target digest does not match admission journal')
        if post_handoff.provider_state_fingerprint != str(journal.get('provider_state_fingerprint') or ''):
            raise ValueError('handoff provider fingerprint does not match admission journal')
        lease_id = str(context.get('lease_id') or '')
        if lease_id:
            ec.record_handoff_lease(ctx.admission_root, token=token, lease_id=lease_id)
        published = ec.snapshot_dir(Path(str(context['evaluate_dir'])))
        digest = str(prepared['snapshot_digest'])
        if not published.is_dir():
            ec.publish_prepared_snapshot(ctx.admission_root, token=token, evaluate_dir=Path(str(context['evaluate_dir'])), expected_digest=digest)
        else:
            ec.load_materialized_corpus(published, expected_digest=digest)
        skip_reasons = dict(prepared.get('skip_reasons') or {})
        if not ec.this_attempt_is_committed(es_path, evaluate_round=int(ctx.candidate_round)):
            existing_done = False
            if es_path.is_file():
                existing_done = str(ec.parse_frontmatter_fields(es_path.read_text(encoding='utf-8')).get('eval_status') or '') == 'done'
            initial = ec.build_initial_evaluate_state_for_corpus(prepared['corpus'], eval_capability=ec._eval_capability(), cycle_type=adapter.detect_cycle_type(cycle_id), evaluate_round=int(context['evaluate_round']), focus_l=str(context.get('session_key') or ''), corpus_digest=digest, corpus_snapshot_ref=str(prepared.get('snapshot_ref') or ec.SNAPSHOT_REF), skipped_ids=list(skip_reasons), skip_reasons=skip_reasons)
            error = ec._commit_staged_evaluate_state(cycle_id, project_root, state=initial, set_phase_evaluating=True, previous_done_required=existing_done)
            if error is not None:
                adapter.abort_eval_admission(cycle_id, project_root, token=token)
                return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, error)
        ec.finalize_admission(ctx.admission_root, token)
        return None
    except Exception as exc:
        if token:
            try:
                adapter.abort_eval_admission(cycle_id, project_root, token=token)
            except Exception:
                pass
        return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, str(exc))

def _validate_evaluate_state_for_session(eval_data: dict[str, str], cycle_id: str, project_root: Path) -> str | None:
    """Return error reason when evaluate-state does not match session at entry."""
    if not ec.is_v8_state(eval_data):
        return 'incompatible_round: evaluate-state is not v8.'
    if eval_data.get('phase') != 'evaluate':
        return f"phase is {eval_data.get('phase')!r}, expected 'evaluate'."
    try:
        expected = ec.build_initial_evaluate_state_for_corpus(ec._load_corpus(cycle_id, project_root), eval_capability=ec._eval_capability(), cycle_type=ec._adapter().detect_cycle_type(cycle_id))
    except ValueError as exc:
        return str(exc)
    for key in ec._ENTRY_V7_KEYS:
        actual = eval_data.get(key)
        exp = expected.get(key)
        if actual != exp:
            return f'{key} is {actual!r}, expected {exp!r} for this session.'
    expected_dimensions = ec.parse_dimension_status(expected['dimension_status'])
    actual_dimensions = ec.parse_dimension_status(eval_data['dimension_status'])
    if set(actual_dimensions) != set(expected_dimensions):
        return f'dimension_status keys are {sorted(actual_dimensions)!r}, expected {sorted(expected_dimensions)!r} for this session.'
    return None

def begin_eval_round(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Enter focus evaluating or start next eval round; return payload."""
    ws_path = ec._adapter().resolve_workflow_state_path(cycle_id, project_root)
    state = ec._adapter().load_workflow_state(cycle_id, project_root)
    current = state['current_state']
    mode = state['mode']
    es_path = ec._evaluate_state_path(cycle_id, project_root)
    if current != ec._EXPECTED_SESSION_STATE:
        return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, f'cannot enter evaluating from state {current!r} (expected {ec._EXPECTED_SESSION_STATE!r}).', current_state=current)
    if ec._focus_phase(cycle_id, project_root) == ec._EXPECTED_FOCUS_PHASE:
        if not es_path.exists():
            admitted = _admit_eval_round(cycle_id, project_root)
            if admitted is not None:
                return admitted
            es_path = ec._evaluate_state_path(cycle_id, project_root)
            if not es_path.exists():
                return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, 'incompatible_round: evaluating without EvalState or admission journal', current_state=current)
        raw_state = ec.parse_frontmatter_fields(es_path.read_text(encoding='utf-8'))
        if not ec.is_v8_state(raw_state):
            return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, 'incompatible_round: evaluate-state must be v8', current_state=current)
        try:
            eval_data = ec.load_evaluate_state(es_path)
        except ValueError as exc:
            return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, str(exc), current_state=current)
        eval_status = eval_data.get('eval_status', '')
        if eval_status == 'done':
            return _start_next_eval_round(cycle_id, project_root, state=state, ws_path=ws_path, mode=mode)
        if eval_status == 'abandoned':
            return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, 'evaluation was abandoned (eval_status: abandoned).', current_state=current)
        mismatch = _validate_evaluate_state_for_session(eval_data, cycle_id, project_root)
        if mismatch:
            return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, mismatch, current_state=current)
        try:
            adapter = ec._adapter()
            ctx = adapter.eval_admission_context(cycle_id, project_root)
            ec.recover_admission(ctx, evaluate_state_path=es_path, evaluate_dir=Path(adapter.eval_paths(cycle_id, project_root, active_doc=adapter.session_context(cycle_id, project_root).active_doc, evaluate_round=ctx.candidate_round, es_path=es_path)['evaluate_dir']), focus_phase=ec._EXPECTED_FOCUS_PHASE)
        except (OSError, ValueError) as exc:
            return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, str(exc), current_state=current)
        return build_eval_loop_payload(cycle_id, project_root)
    incompatible = _v5_incompatible_reason(es_path)
    if incompatible:
        return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, incompatible, current_state=current)
    admitted = _admit_eval_round(cycle_id, project_root)
    if admitted is not None:
        return admitted
    state = ec._adapter().load_workflow_state(cycle_id, project_root)
    es_path = ec._evaluate_state_path(cycle_id, project_root)
    try:
        eval_data = ec.load_evaluate_state(es_path)
    except ValueError as exc:
        return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, str(exc), current_state=state['current_state'])
    mismatch = _validate_evaluate_state_for_session(eval_data, cycle_id, project_root)
    if mismatch:
        return ec._failure(ec._CMD_BEGIN_EVAL_ROUND, mismatch, current_state=state['current_state'])
    return build_eval_loop_payload(cycle_id, project_root)

def init_round(cycle_id: str, project_root: Path, *, mode: str | None=None) -> dict[str, Any]:
    """Retired: admission now goes through begin-eval-round only."""
    del cycle_id, project_root, mode
    return ec._failure(ec._CMD_INIT_ROUND, 'init-round is retired; use begin-eval-round')

def complete_probe_only(cycle_id: str, project_root: Path) -> dict[str, Any]:
    """Finish a probe-only round while preserving pending findings."""
    ctx = ec._load_evaluating_context(cycle_id, project_root)
    if isinstance(ctx, dict):
        ctx['command'] = ec._CMD_COMPLETE_PROBE_ONLY
        return ctx
    (state, _ws_path, eval_data, evaluate_round, active_doc, _mode) = ctx
    if eval_data.get('eval_capability') != 'probe-only':
        return ec._failure(ec._CMD_COMPLETE_PROBE_ONLY, 'complete-probe-only requires probe-only capability')
    dimensions = ec.parse_dimension_status(eval_data['dimension_status'])
    active_dimensions = {dim_id: status for (dim_id, status) in dimensions.items() if status != 'skipped'}
    terminal_replay = eval_data.get('eval_phase') == 'done' and eval_data.get('eval_status') == 'done'
    if not terminal_replay and eval_data.get('eval_phase') != 'probe':
        return ec._failure(ec._CMD_COMPLETE_PROBE_ONLY, 'eval_phase must be probe or done')
    if any((status not in {'probed', 'complete'} for status in active_dimensions.values())):
        return ec._failure(ec._CMD_COMPLETE_PROBE_ONLY, 'not all dimensions are probed')
    paths = ec._eval_paths(cycle_id, project_root, active_doc=active_doc, evaluate_round=evaluate_round, es_path=ec._evaluate_state_path(cycle_id, project_root))
    operations = ec._operations_for_round(paths, eval_data['round_token'])
    if any((record.get('operation_kind') == 'probe' and record.get('phase') != 'committed' for record in operations)):
        return ec._failure(ec._CMD_COMPLETE_PROBE_ONLY, 'open probe operation remains')
    committed_probe_dimensions = {str(record.get('dimension_id')) for record in operations if record.get('operation_kind') == 'probe' and record.get('phase') == 'committed'}
    if not set(active_dimensions) <= committed_probe_dimensions:
        return ec._failure(ec._CMD_COMPLETE_PROBE_ONLY, 'missing committed probe operation for one or more dimensions')
    rows_by_dimension: dict[str, list[dict[str, str]]] = {}
    review_paths: list[str] = []
    for dimension_id in active_dimensions:
        review_path = ec._review_path_from_context(cycle_id, project_root, state=state, evaluate_round=evaluate_round, active_doc=active_doc, dim=dimension_id)
        if not review_path.is_file():
            return ec._failure(ec._CMD_COMPLETE_PROBE_ONLY, f'ReviewFile missing for dimension {dimension_id!r}')
        try:
            rows_by_dimension[dimension_id] = ec.parse_review_file(review_path, expected_dimension_id=dimension_id, expected_round_token=eval_data['round_token'])
        except ValueError as exc:
            return ec._failure(ec._CMD_COMPLETE_PROBE_ONLY, str(exc))
        review_paths.append(review_path.as_posix())
    try:
        issues = ec.canonical_probe_findings_from_reviews(rows_by_dimension, operations, expected_dimensions=list(active_dimensions))
    except ValueError as exc:
        return ec._failure(ec._CMD_COMPLETE_PROBE_ONLY, str(exc))
    if terminal_replay:
        return ec._success(ec._CMD_COMPLETE_PROBE_ONLY, eval_phase='done', eval_status='done', idempotent=True, issues=issues, review_paths=review_paths)
    corpus = ec._load_corpus(cycle_id, project_root)

    def _finish(data: dict[str, str]) -> dict[str, str]:
        updated = dict(data)
        for dimension_id in active_dimensions:
            updated = ec.merge_current_dimension(updated, dimension_id, 'complete', corpus=corpus)
        updated['eval_phase'] = 'done'
        updated['eval_status'] = 'done'
        return updated
    error = ec._commit_staged_evaluate_state(cycle_id, project_root, update=_finish)
    if error is not None:
        return ec._failure(ec._CMD_COMPLETE_PROBE_ONLY, error)
    return ec._success(ec._CMD_COMPLETE_PROBE_ONLY, eval_phase='done', eval_status='done', idempotent=False, issues=issues, review_paths=review_paths)
