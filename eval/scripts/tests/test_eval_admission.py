"""Tests for admission journal, skip machinery, and begin-dimension skip."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval_admission import (  # noqa: E402
    EvalAdmissionContext,
    can_abort_admission,
    discard_published_snapshot,
    finalize_admission,
    load_journal,
    mark_prepared,
    mark_transitioned,
    record_handoff_lease,
    recover_admission,
    reserve_journal,
    stable_runtime_fingerprint,
    this_attempt_is_committed,
)
from evaluate_state_schema import (  # noqa: E402
    build_initial_evaluate_state,
    parse_dimension_status,
    parse_skip_reason,
    validate_evaluate_state,
)
import eval_control  # noqa: E402


def test_reserve_journal_is_create_if_absent(tmp_path: Path) -> None:
    ctx = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="pending",
        target_path=tmp_path / "t.md",
        target_digest="d",
        candidate_round=1,
    )
    first = reserve_journal(ctx, token="tok-1")
    second = reserve_journal(ctx, token="tok-2")
    assert first["token"] == "tok-1"
    assert second["token"] == "tok-1"
    assert load_journal(tmp_path)["status"] == "preparing"


def test_recover_committed_state_cleans_journal(tmp_path: Path) -> None:
    target = tmp_path / "t.md"
    target.write_text("t", encoding="utf-8")
    ctx = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="pending",
        target_path=target,
        target_digest="d",
        candidate_round=1,
    )
    reserve_journal(ctx, token="tok-1")
    mark_prepared(ctx, token="tok-1", snapshot_digest="deadbeef")
    es = tmp_path / "evaluate-state.md"
    es.write_text(
        "---\nversion: 8\ncorpus_digest: deadbeef\n"
        "corpus_snapshot_ref: corpus-snapshot/manifest.json\n---\n",
        encoding="utf-8",
    )
    snap = tmp_path / "round" / "corpus-snapshot"
    snap.mkdir(parents=True)
    # recover requires a valid snapshot when state is a commit marker
    with pytest.raises(ValueError, match="incompatible_round"):
        recover_admission(
            ctx,
            evaluate_state_path=es,
            evaluate_dir=tmp_path / "round",
            focus_phase="evaluating",
        )


def test_abort_allowed_when_commit_marker_is_previous_round(tmp_path: Path) -> None:
    es = tmp_path / "evaluate-state.md"
    es.write_text(
        "---\nversion: 8\ncorpus_digest: olddigest\n"
        "corpus_snapshot_ref: corpus-snapshot/manifest.json\n---\n",
        encoding="utf-8",
    )
    journal = {
        "token": "tok-2",
        "status": "prepared",
        "candidate_round": 2,
        "snapshot_digest": "newdigest",
    }
    assert (
        can_abort_admission(
            journal=journal,
            token="tok-2",
            evaluate_state_path=es,
            operations_path=tmp_path / "eval-operations.json",
        )
        is True
    )


def test_abort_refused_when_commit_marker_matches_journal(tmp_path: Path) -> None:
    es = tmp_path / "evaluate-state.md"
    es.write_text(
        "---\nversion: 8\ncorpus_digest: samedigest\n"
        "corpus_snapshot_ref: corpus-snapshot/manifest.json\n---\n",
        encoding="utf-8",
    )
    journal = {
        "token": "tok-1",
        "status": "transitioned",
        "candidate_round": 1,
        "snapshot_digest": "samedigest",
    }
    assert (
        can_abort_admission(
            journal=journal,
            token="tok-1",
            evaluate_state_path=es,
            operations_path=tmp_path / "eval-operations.json",
        )
        is False
    )


def test_abort_refused_after_probe_operation(tmp_path: Path) -> None:
    journal = {"token": "tok-1", "status": "transitioned"}
    ops = tmp_path / "operation-records.json"
    ops.write_text(
        json.dumps({"records": [{"operation_kind": "probe"}]}),
        encoding="utf-8",
    )
    assert (
        can_abort_admission(
            journal=journal,
            token="tok-1",
            evaluate_state_path=tmp_path / "missing.md",
            operations_path=ops,
        )
        is False
    )


def test_skipped_dimension_requires_reason() -> None:
    state = build_initial_evaluate_state(
        dimension_ids=["keep", "skip"],
        eval_capability="full-remediation",
        handling_policy={"keep": "class-default", "skip": "human-first"},
        skipped_ids=["skip"],
        skip_reasons={"skip": "empty_intent_baseline_refs"},
        corpus_digest="abc",
        corpus_snapshot_ref="corpus-snapshot/manifest.json",
    )
    assert parse_dimension_status(state["dimension_status"]) == {
        "keep": "pending",
        "skip": "skipped",
    }
    assert parse_skip_reason(state["skip_reason"]) == {
        "skip": "empty_intent_baseline_refs",
    }
    state["eval_phase"] = "done"
    state["eval_status"] = "done"
    state["dimension_status"] = '{"keep":"complete","skip":"skipped"}'
    assert validate_evaluate_state(state) == []


def test_begin_dimension_returns_skip_without_operation(monkeypatch, tmp_path: Path) -> None:
    eval_data = build_initial_evaluate_state(
        dimension_ids=["keep", "skip"],
        eval_capability="probe-only",
        handling_policy={"keep": "class-default", "skip": "human-first"},
        skipped_ids=["skip"],
        skip_reasons={"skip": "empty_norm_constraint_refs"},
        corpus_digest="abc",
        corpus_snapshot_ref="corpus-snapshot/manifest.json",
    )
    eval_data["eval_phase"] = "probe"

    class _Adapter:
        pass

    monkeypatch.setattr(
        eval_control,
        "_load_evaluating_context",
        lambda *_args, **_kwargs: (
            {"current_state": "Working"},
            tmp_path / "ws.md",
            eval_data,
            1,
            1,
            "tech",
        ),
    )
    monkeypatch.setattr(eval_control, "_dispatch_dim_allowed", lambda *_a, **_k: True)
    monkeypatch.setattr(eval_control, "_canonical_dim", lambda *_a, **_k: "skip")
    monkeypatch.setattr(eval_control, "_load_corpus", lambda *_a, **_k: {})
    monkeypatch.setattr(
        eval_control,
        "_eval_paths",
        lambda *_a, **_k: {"evaluate_dir": tmp_path.as_posix()},
    )
    monkeypatch.setattr(
        eval_control,
        "_evaluate_state_path",
        lambda *_a, **_k: tmp_path / "evaluate-state.md",
    )
    result = eval_control.begin_dimension("C1", tmp_path, dim="skip")
    assert result["ok"] is True
    assert result["skip"] is True
    assert result["skip_reason"] == "empty_norm_constraint_refs"
    assert "operation_ctx" not in result


def test_mark_prepared_pins_skip_reasons(tmp_path: Path) -> None:
    ctx = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="pending",
        target_path=tmp_path / "t.md",
        target_digest="d",
        candidate_round=1,
    )
    reserve_journal(ctx, token="tok-1")
    journal = mark_prepared(
        ctx,
        token="tok-1",
        snapshot_digest="deadbeef",
        skip_reasons={"intent-fidelity": "empty_intent_baseline_refs"},
    )
    assert journal["skip_reasons"] == {
        "intent-fidelity": "empty_intent_baseline_refs",
    }
    assert load_journal(tmp_path)["skip_reasons"]["intent-fidelity"] == (
        "empty_intent_baseline_refs"
    )


def test_prepared_provider_drift_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "t.md"
    target.write_text("t", encoding="utf-8")
    ctx = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="pending",
        target_path=target,
        target_digest="d",
        candidate_round=1,
    )
    reserve_journal(ctx, token="tok-1")
    mark_prepared(ctx, token="tok-1", snapshot_digest="deadbeef")
    drifted = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="changed",
        previous_phase="pending",
        target_path=target,
        target_digest="d",
        candidate_round=1,
    )
    with pytest.raises(ValueError, match="drifted after prepare"):
        recover_admission(
            drifted,
            evaluate_state_path=tmp_path / "missing.md",
            evaluate_dir=tmp_path / "round",
            focus_phase="pending",
        )
    assert load_journal(tmp_path) is not None


def test_other_round_evalstate_without_journal_is_fresh(tmp_path: Path) -> None:
    target = tmp_path / "t.md"
    target.write_text("t", encoding="utf-8")
    ctx = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="Evaluating",
        target_path=target,
        target_digest="d",
        candidate_round=2,
    )
    es = tmp_path / "evaluate-state.md"
    es.write_text(
        "---\nversion: 8\nevaluate_round: 1\ncorpus_digest: olddigest\n"
        "corpus_snapshot_ref: corpus-snapshot/manifest.json\n---\n",
        encoding="utf-8",
    )
    recovered = recover_admission(
        ctx,
        evaluate_state_path=es,
        evaluate_dir=tmp_path / "round2",
        focus_phase="evaluating",
    )
    assert recovered["action"] == "fresh"
    assert this_attempt_is_committed(es, evaluate_round=2) is False


def test_same_round_journal_ignores_other_round_evalstate(tmp_path: Path) -> None:
    target = tmp_path / "t.md"
    target.write_text("t", encoding="utf-8")
    ctx = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="Evaluating",
        target_path=target,
        target_digest="d",
        candidate_round=2,
    )
    reserve_journal(ctx, token="tok-2")
    mark_prepared(ctx, token="tok-2", snapshot_digest="newdigest")
    es = tmp_path / "evaluate-state.md"
    es.write_text(
        "---\nversion: 8\nevaluate_round: 1\ncorpus_digest: olddigest\n"
        "corpus_snapshot_ref: corpus-snapshot/manifest.json\n---\n",
        encoding="utf-8",
    )
    recovered = recover_admission(
        ctx,
        evaluate_state_path=es,
        evaluate_dir=tmp_path / "round2",
        focus_phase="pending",
    )
    assert recovered["action"] == "transition"
    assert load_journal(tmp_path) is not None


def test_finalize_when_this_attempt_committed(tmp_path: Path) -> None:
    ctx = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="Writing",
        target_path=tmp_path / "t.md",
        target_digest="d",
        candidate_round=1,
    )
    reserve_journal(ctx, token="tok-1")
    mark_prepared(ctx, token="tok-1", snapshot_digest="samedigest")
    es = tmp_path / "evaluate-state.md"
    es.write_text(
        "---\nversion: 8\nevaluate_round: 1\ncorpus_digest: samedigest\n"
        "corpus_snapshot_ref: corpus-snapshot/manifest.json\n---\n",
        encoding="utf-8",
    )
    assert this_attempt_is_committed(es, evaluate_round=1) is True
    finalize_admission(tmp_path, "tok-1")
    assert load_journal(tmp_path) is None


def test_stale_journal_from_other_candidate_is_discarded(tmp_path: Path) -> None:
    target = tmp_path / "t.md"
    target.write_text("t", encoding="utf-8")
    leftover = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="Writing",
        target_path=target,
        target_digest="d",
        candidate_round=2,
    )
    reserve_journal(leftover, token="tok-2")
    mark_prepared(leftover, token="tok-2", snapshot_digest="round2")
    nxt = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="Evaluating",
        target_path=target,
        target_digest="d",
        candidate_round=3,
    )
    es = tmp_path / "evaluate-state.md"
    es.write_text(
        "---\nversion: 8\nevaluate_round: 2\ncorpus_digest: round2\n"
        "corpus_snapshot_ref: corpus-snapshot/manifest.json\n---\n",
        encoding="utf-8",
    )
    recovered = recover_admission(
        nxt,
        evaluate_state_path=es,
        evaluate_dir=tmp_path / "round3",
        focus_phase="evaluating",
    )
    assert recovered["action"] == "fresh"
    assert load_journal(tmp_path) is None


def test_evaluating_without_journal_or_evalstate_is_incompatible(
    tmp_path: Path,
) -> None:
    target = tmp_path / "t.md"
    target.write_text("t", encoding="utf-8")
    ctx = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="Writing",
        target_path=target,
        target_digest="d",
        candidate_round=1,
    )
    with pytest.raises(ValueError, match="evaluating without EvalState"):
        recover_admission(
            ctx,
            evaluate_state_path=tmp_path / "missing.md",
            evaluate_dir=tmp_path / "round",
            focus_phase="evaluating",
        )


def test_stable_runtime_fingerprint_ignores_lease_fields() -> None:
    base = {
        "version": 1,
        "focus_phase": "evaluating",
        "evaluate_round": 2,
        "active_lease_id": "lease-a",
        "write_staging_dir": "/tmp/a",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    changed_lease = dict(base)
    changed_lease["active_lease_id"] = "lease-b"
    changed_lease["write_staging_dir"] = "/tmp/b"
    changed_lease["updated_at"] = "2026-01-02T00:00:00+00:00"
    assert stable_runtime_fingerprint(base) == stable_runtime_fingerprint(
        changed_lease
    )
    drifted = dict(base)
    drifted["evaluate_round"] = 3
    assert stable_runtime_fingerprint(base) != stable_runtime_fingerprint(drifted)


def test_record_handoff_lease_pins_journal_lease(tmp_path: Path) -> None:
    ctx = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="Writing",
        target_path=tmp_path / "t.md",
        target_digest="d",
        candidate_round=1,
    )
    reserve_journal(ctx, token="tok-1")
    mark_prepared(ctx, token="tok-1", snapshot_digest="deadbeef")
    mark_transitioned(tmp_path, token="tok-1")
    journal = record_handoff_lease(tmp_path, token="tok-1", lease_id="lease-9")
    assert journal["lease_id"] == "lease-9"
    assert load_journal(tmp_path)["lease_id"] == "lease-9"


def test_prepared_fingerprint_drift_allowed_after_transition(tmp_path: Path) -> None:
    target = tmp_path / "t.md"
    target.write_text("t", encoding="utf-8")
    ctx = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="Writing",
        target_path=target,
        target_digest="d",
        candidate_round=1,
    )
    reserve_journal(ctx, token="tok-1")
    mark_prepared(ctx, token="tok-1", snapshot_digest="deadbeef")
    drifted = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="after-transition",
        previous_phase="Writing",
        target_path=target,
        target_digest="d",
        candidate_round=1,
    )
    recovered = recover_admission(
        drifted,
        evaluate_state_path=tmp_path / "missing.md",
        evaluate_dir=tmp_path / "round",
        focus_phase="evaluating",
    )
    assert recovered["action"] == "publish"


def test_transitioned_fingerprint_drift_is_rejected(tmp_path: Path) -> None:
    target = tmp_path / "t.md"
    target.write_text("t", encoding="utf-8")
    ctx = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="abc",
        previous_phase="Writing",
        target_path=target,
        target_digest="d",
        candidate_round=1,
    )
    reserve_journal(ctx, token="tok-1")
    mark_prepared(ctx, token="tok-1", snapshot_digest="deadbeef")
    mark_transitioned(tmp_path, token="tok-1", provider_state_fingerprint="after")
    drifted = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="changed-again",
        previous_phase="Writing",
        target_path=target,
        target_digest="d",
        candidate_round=1,
    )
    with pytest.raises(ValueError, match="drifted after prepare"):
        recover_admission(
            drifted,
            evaluate_state_path=tmp_path / "missing.md",
            evaluate_dir=tmp_path / "round",
            focus_phase="evaluating",
        )


def test_mark_transitioned_refreshes_fingerprint(tmp_path: Path) -> None:
    ctx = EvalAdmissionContext(
        admission_root=tmp_path,
        session_key="L1",
        provider_state_fingerprint="before",
        previous_phase="Writing",
        target_path=tmp_path / "t.md",
        target_digest="d",
        candidate_round=1,
    )
    reserve_journal(ctx, token="tok-1")
    mark_prepared(ctx, token="tok-1", snapshot_digest="deadbeef")
    journal = mark_transitioned(
        tmp_path,
        token="tok-1",
        provider_state_fingerprint="after",
    )
    assert journal["status"] == "transitioned"
    assert journal["provider_state_fingerprint"] == "after"


def test_discard_published_snapshot_removes_corpus_snapshot(tmp_path: Path) -> None:
    evaluate_dir = tmp_path / "evaluate1"
    snap = evaluate_dir / "corpus-snapshot"
    snap.mkdir(parents=True)
    (snap / "manifest.json").write_text("{}", encoding="utf-8")
    discard_published_snapshot(evaluate_dir)
    assert not snap.exists()


def test_init_round_is_retired(tmp_path: Path) -> None:
    result = eval_control.init_round("C1", tmp_path)
    assert result["ok"] is False
    assert "retired" in result["reason"]


def test_remediation_complete_ignores_skipped_dimensions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    eval_data = {
        "eval_phase": "remediation",
        "eval_capability": "full-remediation",
        "round_token": "rt-1",
        "dimension_status": '{"keep":"probed","intent-fidelity":"skipped"}',
    }
    review = tmp_path / "keep.md"
    review.write_text("review", encoding="utf-8")
    monkeypatch.setattr(
        eval_control,
        "_remediation_command_context",
        lambda *_args, **_kwargs: (
            {"current_state": "Working"},
            eval_data,
            1,
            1,
            {"evaluate_dir": tmp_path.as_posix()},
        ),
    )
    monkeypatch.setattr(
        eval_control,
        "_dispatch_canonical",
        lambda *_args, **_kwargs: ["keep", "intent-fidelity"],
    )
    monkeypatch.setattr(
        eval_control,
        "_operations_for_round",
        lambda *_args, **_kwargs: [
            {
                "operation_kind": "probe",
                "phase": "committed",
                "dimension_id": "keep",
            }
        ],
    )
    monkeypatch.setattr(
        eval_control,
        "_review_path_from_context",
        lambda *_args, **_kwargs: review,
    )
    monkeypatch.setattr(eval_control, "parse_review_file", lambda *_a, **_k: [])
    monkeypatch.setattr(
        eval_control,
        "validate_review_against_probe_record",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        eval_control,
        "validate_review_completion",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(eval_control, "_load_corpus", lambda *_a, **_k: {})
    monkeypatch.setattr(
        eval_control,
        "merge_current_dimension",
        lambda data, *_a, **_k: data,
    )
    monkeypatch.setattr(eval_control, "patch_issue_count", lambda data, *_a, **_k: data)
    monkeypatch.setattr(eval_control, "_recompute_aggregate_counts", lambda data: data)
    monkeypatch.setattr(eval_control, "count_resolved", lambda _rows: 0)
    monkeypatch.setattr(
        eval_control,
        "_commit_staged_evaluate_state",
        lambda *_a, **_k: None,
    )
    result = eval_control.remediation_complete("C1", tmp_path)
    assert result["ok"] is True
    assert result["eval_status"] == "done"
