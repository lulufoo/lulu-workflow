#!/usr/bin/env python3
"""Admission steps for the lulu-tasks Eval adapter."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[1]
_EVAL_SCRIPTS = Path(__file__).resolve().parents[3] / "eval" / "scripts"
for _path in (_SCRIPTS, _EVAL_SCRIPTS):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from corpus_schema import expand_corpus
from corpus_snapshot import SNAPSHOT_REF
from eval_admission import (
    can_abort_admission,
    delete_journal,
    discard_lease_dir,
    discard_published_snapshot,
    discard_staging,
    load_journal,
    mark_prepared,
    mark_transitioned,
    prepare_snapshot,
    reserve_journal,
)
from tt_eval_runtime_schema import (
    enter_evaluating_runtime,
    evaluate_dir,
    evaluate_state_path,
    load_runtime,
    runtime_path,
)


def prepare_eval_admission(adapter: Any, cycle_id: str, project_root: Path) -> dict[str, Any]:
    ctx = adapter.eval_admission_context(cycle_id, project_root)
    journal = reserve_journal(ctx)
    token = str(journal["token"])
    try:
        corpus = expand_corpus(
            adapter.resolve_eval_corpus(cycle_id, project_root),
            {
                "eval_target_path": ctx.target_path.as_posix(),
                "M": str(ctx.candidate_round),
            },
        )
        manifest = prepare_snapshot(
            ctx,
            token=token,
            corpus=corpus,
            method_roots=adapter.method_roots(),
            method_must_stay_under=adapter.workflow_root(),
            sot_roots=[project_root.resolve()],
        )
        mark_prepared(ctx, token=token, snapshot_digest=str(manifest["corpus_digest"]))
    except Exception:
        discard_staging(ctx.admission_root, token)
        if str(journal.get("status")) == "preparing":
            delete_journal(ctx.admission_root)
        raise
    session_dir = adapter.session_dir(cycle_id, project_root)
    return {
        "ok": True,
        "token": token,
        "corpus": corpus,
        "skip_reasons": {},
        "snapshot_digest": str(manifest["corpus_digest"]),
        "snapshot_ref": SNAPSHOT_REF,
        "evaluate_dir": evaluate_dir(session_dir, ctx.candidate_round).resolve().as_posix(),
        "context": ctx,
    }


def abort_eval_admission(
    adapter: Any,
    cycle_id: str,
    project_root: Path,
    *,
    token: str,
) -> dict[str, Any]:
    session_dir = adapter.session_dir(cycle_id, project_root)
    journal = load_journal(session_dir)
    if journal is None:
        return {"ok": True, "aborted": False}
    evaluate_round = int(journal.get("candidate_round") or 1)
    if not can_abort_admission(
        journal=journal,
        token=token,
        evaluate_state_path=evaluate_state_path(session_dir),
        operations_path=evaluate_dir(session_dir, evaluate_round) / "eval-operations.json",
    ):
        return {"ok": False, "error": "admission abort refused"}
    discard_published_snapshot(evaluate_dir(session_dir, evaluate_round))
    runtime = load_runtime(runtime_path(session_dir))
    previous = str(journal.get("previous_phase") or "")
    if str(journal.get("status")) == "transitioned" and previous not in {
        "evaluating",
        "Evaluating",
    }:
        runtime["focus_phase"] = previous or "pending"
        runtime["evaluate_round"] = max(0, evaluate_round - 1)
    lease_id = str(journal.get("lease_id") or runtime.get("active_lease_id") or "")
    discard_lease_dir(session_dir / "eval" / "staging", lease_id)
    runtime["active_lease_id"] = ""
    runtime["write_staging_dir"] = ""
    adapter.save_runtime(cycle_id, project_root, runtime)
    discard_staging(session_dir, token)
    delete_journal(session_dir)
    return {"ok": True, "aborted": True}


def enter_evaluating(
    adapter: Any,
    cycle_id: str,
    project_root: Path,
    *,
    admission_token: str | None = None,
) -> dict[str, Any]:
    session_dir = adapter.session_dir(cycle_id, project_root)
    runtime = load_runtime(runtime_path(session_dir))
    try:
        adapter.ensure_eval_target(cycle_id, project_root)
    except (FileNotFoundError, ValueError) as exc:
        return {
            "ok": False,
            "current_state": "Working",
            "transitioned": False,
            "error": f"eval target bind failed: {exc}",
        }
    already = runtime.get("focus_phase") == "evaluating"
    runtime = enter_evaluating_runtime(runtime)
    evaluate_round = int(runtime["evaluate_round"])
    evaluate_dir(session_dir, evaluate_round).mkdir(parents=True, exist_ok=True)
    adapter.save_runtime(cycle_id, project_root, runtime)
    if admission_token:
        mark_transitioned(
            session_dir,
            token=admission_token,
            provider_state_fingerprint=adapter.provider_fingerprint(session_dir),
        )
    return {
        "ok": True,
        "current_state": "Working",
        "transitioned": not already,
        "evaluate_round": evaluate_round,
        "focus": "tasks",
    }
