#!/usr/bin/env python3
"""Compose fact-intake-eval WorkflowAdapter — independent task; B=_facts.json."""

from __future__ import annotations

import hashlib
import os
import shutil
import sys
from pathlib import Path
from typing import Any

_INTAKE_EVAL_SCRIPTS = Path(__file__).resolve().parent
_WORKFLOW_ROOT = Path(__file__).resolve().parents[4]
_EVAL_SCRIPTS = _WORKFLOW_ROOT / "eval" / "scripts"
_COMPOSE_KERNEL = _WORKFLOW_ROOT / "compose" / "scripts" / "_kernel"
_COMPOSE_SESSION = _WORKFLOW_ROOT / "compose" / "scripts" / "session"
_COMPOSE_FACTS = _WORKFLOW_ROOT / "compose" / "scripts" / "facts"
_COMPOSE_SCOPE = _WORKFLOW_ROOT / "compose" / "scripts" / "scope"
_COMPOSE_SCHEMA_SESSION = (
    _WORKFLOW_ROOT / "compose" / "scripts" / "schema" / "session"
)
# Compose schema/session also ships eval_handoff_schema.py — keep Eval scripts
# ahead of that directory so the shared Eval handoff helpers win.
for p in (
    _INTAKE_EVAL_SCRIPTS,
    _COMPOSE_KERNEL,
    _COMPOSE_SESSION,
    _COMPOSE_FACTS,
    _COMPOSE_SCOPE,
    _COMPOSE_SCHEMA_SESSION,
    _EVAL_SCRIPTS,
):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from fact_intake_eval_runtime_schema import (  # noqa: E402
    allocate_lease,
    enter_evaluating_runtime,
    evaluate_dir,
    evaluate_state_path,
    fact_intake_eval_root,
    hard_blocked,
    load_runtime,
    load_workflow_state_view,
    runtime_path,
    save_runtime,
    workflow_state_view_path,
    write_workflow_state_file,
)
from compose_session import workflow_state_path as compose_workflow_state_path  # noqa: E402
from corpus_compose import compose_corpus, load_dimension_def  # noqa: E402
from l_ledger_schema import active_slice_dir  # noqa: E402
from eval_handoff_schema import (  # noqa: E402
    build_eval_handoff_v2,
    validate_artifact_manifest_v2,
    validate_eval_handoff_v2,
)
from corpus_schema import expand_corpus  # noqa: E402
from corpus_snapshot import SNAPSHOT_REF  # noqa: E402
from eval_admission import (  # noqa: E402
    EvalAdmissionContext,
    can_abort_admission,
    delete_journal,
    discard_lease_dir,
    discard_published_snapshot,
    discard_staging,
    file_digest,
    fingerprint_parts,
    load_journal,
    mark_prepared,
    mark_transitioned,
    prepare_snapshot,
    reserve_journal,
    stable_runtime_fingerprint,
)
from evaluate_state_schema import load_evaluate_state, save_evaluate_state  # noqa: E402
from facts_schema import facts_path  # noqa: E402
from resolved_refs_schema import has_resolved_refs, resolved_scope_ref  # noqa: E402
from scope_package_convert import (  # noqa: E402
    ScopePackageAntiseepError,
    focus_seed_source_path,
    revision_uses_scope_package,
)
from workflow_adapter import SessionContext  # noqa: E402
from workflow_common import parse_frontmatter_fields  # noqa: E402

_WORKFLOW_ID = "compose-fact-intake-eval"
_CORPUS_ID = "compose-fact-intake-eval-composed"
_CORPUS_VERSION = "2"
_CORPUS_REF = f"{_CORPUS_ID}@{_CORPUS_VERSION}"
_DIMENSION_ORDER = ("e1-doc-coverage", "e2-fact-provenance")
_PROFILE_ENV = "COMPOSE_FACT_INTAKE_PROFILE_ID"
_EVAL_CAPABILITY = "full-remediation"


def _profile_id() -> str:
    pid = (os.environ.get(_PROFILE_ENV) or "").strip()
    if not pid:
        raise ValueError(
            f"{_PROFILE_ENV} is required (set by fact_intake_eval_control)",
        )
    return pid


def _revision_dir(cycle_id: str, project_root: Path) -> Path:
    return compose_workflow_state_path(
        cycle_id, project_root.resolve(), _profile_id()
    ).parent.resolve()


def _slice_dir(cycle_id: str, project_root: Path) -> Path:
    return active_slice_dir(_revision_dir(cycle_id, project_root))


def _source_path(revision_dir: Path) -> str:
    try:
        if revision_uses_scope_package(revision_dir):
            return focus_seed_source_path(revision_dir)
        if has_resolved_refs(revision_dir):
            ref = resolved_scope_ref(revision_dir)
            if ref is not None:
                return ref.path
    except ScopePackageAntiseepError:
        return ""
    return ""


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_replace(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    os.replace(src, dest)


class FactIntakeEvalAdapter:
    """WorkflowAdapter for Fact-intake eval (Deductive intake; return_to_caller)."""

    WORKFLOW_ID = _WORKFLOW_ID

    def _runtime(self, cycle_id: str, project_root: Path) -> dict[str, Any]:
        return load_runtime(runtime_path(_slice_dir(cycle_id, project_root)))

    def _save_runtime(
        self, cycle_id: str, project_root: Path, runtime: dict[str, Any]
    ) -> None:
        slice_dir = _slice_dir(cycle_id, project_root)
        save_runtime(runtime_path(slice_dir), runtime)
        write_workflow_state_file(workflow_state_view_path(slice_dir), runtime)

    def resolve_workflow_state_path(
        self, cycle_id: str, project_root: Path
    ) -> Path:
        return workflow_state_view_path(_slice_dir(cycle_id, project_root))

    def load_workflow_state(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, str]:
        # Keep compose session Working; Fact-intake eval uses synthetic view.
        compose_ws = compose_workflow_state_path(
            cycle_id, project_root.resolve(), _profile_id()
        )
        if compose_ws.is_file():
            fields = parse_frontmatter_fields(compose_ws.read_text(encoding="utf-8"))
            if fields.get("current_state") not in {"Working", ""}:
                return {
                    "version": "1",
                    "workflow": _WORKFLOW_ID,
                    "mode": "tech",
                    "cycle_type": "feature",
                    "current_state": str(fields.get("current_state") or ""),
                    "evaluate_round": "0",
                    "updated_at": "",
                }
        return load_workflow_state_view(self._runtime(cycle_id, project_root))

    def save_workflow_state(
        self,
        cycle_id: str,
        project_root: Path,
        updates: dict[str, str],
        *,
        merge: bool = True,
    ) -> None:
        del merge
        runtime = self._runtime(cycle_id, project_root)
        if "evaluate_round" in updates:
            runtime["evaluate_round"] = int(updates["evaluate_round"] or 0)
        self._save_runtime(cycle_id, project_root, runtime)

    def resolve_evaluate_state_path(
        self, cycle_id: str, project_root: Path
    ) -> Path:
        return evaluate_state_path(_slice_dir(cycle_id, project_root))

    def session_context(
        self, cycle_id: str, project_root: Path
    ) -> SessionContext:
        runtime = self._runtime(cycle_id, project_root)
        return SessionContext(
            active_doc=1,
            mode="tech",
            upstream_baseline_ref="",
            cycle_type="feature",
            focus_phase=str(runtime.get("focus_phase") or "pending"),
        )

    def eval_paths(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        active_doc: int,
        evaluate_round: int,
        es_path: Path,
    ) -> dict[str, str]:
        del active_doc
        slice_dir = _slice_dir(cycle_id, project_root)
        revision_dir = _revision_dir(cycle_id, project_root)
        target = facts_path(slice_dir).resolve()
        return {
            "eval_target_path": target.as_posix(),
            "compose_doc": target.as_posix(),
            "facts_path": target.as_posix(),
            "scope_doc": _source_path(revision_dir),
            "evaluate_state": es_path.resolve().as_posix(),
            "evaluate_dir": evaluate_dir(slice_dir, evaluate_round)
            .resolve()
            .as_posix(),
        }

    def corpus_ref_for_mode(self, mode: str) -> str:
        del mode
        return _CORPUS_REF

    def dimension_defs_dir(self) -> Path:
        return _WORKFLOW_ROOT / "compose" / "fact-intake-runner" / "fact-intake-eval" / "dimension-defs"

    def resolve_eval_corpus(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, Any]:
        del cycle_id, project_root
        dims_dir = self.dimension_defs_dir()
        dimensions = [
            load_dimension_def(dims_dir / f"{dim_id}.json")
            for dim_id in _DIMENSION_ORDER
        ]
        return compose_corpus(
            corpus_id=_CORPUS_ID,
            corpus_version=_CORPUS_VERSION,
            scope="compose-fact-intake-eval",
            dimensions=dimensions,
            review_output_prefix="fact-intake-review",
        )

    def corpus_bind_extensions(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, str]:
        slice_dir = _slice_dir(cycle_id, project_root)
        revision_dir = _revision_dir(cycle_id, project_root)
        facts = facts_path(slice_dir).resolve().as_posix()
        source = _source_path(revision_dir)
        return {
            "facts_path": facts,
            "scope_doc": source,
            "source_path": source,
            "eval_target_path": facts,
        }

    def detect_cycle_type(self, cycle_id: str) -> str:
        del cycle_id
        return "feature"

    def eval_admission_context(
        self, cycle_id: str, project_root: Path
    ) -> EvalAdmissionContext:
        slice_dir = _slice_dir(cycle_id, project_root)
        runtime = self._runtime(cycle_id, project_root)
        target = facts_path(slice_dir).resolve()
        if not target.is_file():
            raise ValueError(f"_facts.json missing: {target}")
        current = int(runtime.get("evaluate_round") or 0)
        already = runtime.get("focus_phase") == "evaluating"
        return EvalAdmissionContext(
            admission_root=fact_intake_eval_root(slice_dir),
            session_key=str(slice_dir.name),
            provider_state_fingerprint=self._provider_fingerprint(slice_dir),
            previous_phase=str(runtime.get("focus_phase") or "pending"),
            target_path=target,
            target_digest=file_digest(target),
            candidate_round=current if already and current >= 1 else current + 1,
        )

    def prepare_eval_admission(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, Any]:
        ctx = self.eval_admission_context(cycle_id, project_root)
        journal = reserve_journal(ctx)
        token = str(journal["token"])
        try:
            bind = self.corpus_bind_extensions(cycle_id, project_root)
            bind["M"] = str(ctx.candidate_round)
            corpus = expand_corpus(self.resolve_eval_corpus(cycle_id, project_root), bind)
            manifest = prepare_snapshot(
                ctx,
                token=token,
                corpus=corpus,
                method_roots=[_WORKFLOW_ROOT, _WORKFLOW_ROOT.parent],
                method_must_stay_under=_WORKFLOW_ROOT,
                sot_roots=[project_root.resolve()],
            )
            mark_prepared(ctx, token=token, snapshot_digest=str(manifest["corpus_digest"]))
        except Exception:
            discard_staging(ctx.admission_root, token)
            if str(journal.get("status")) == "preparing":
                delete_journal(ctx.admission_root)
            raise
        slice_dir = _slice_dir(cycle_id, project_root)
        return {
            "ok": True,
            "token": token,
            "corpus": corpus,
            "skip_reasons": {},
            "snapshot_digest": str(manifest["corpus_digest"]),
            "snapshot_ref": SNAPSHOT_REF,
            "evaluate_dir": evaluate_dir(slice_dir, ctx.candidate_round)
            .resolve()
            .as_posix(),
            "context": ctx,
        }

    def abort_eval_admission(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        token: str,
    ) -> dict[str, Any]:
        slice_dir = _slice_dir(cycle_id, project_root)
        admission_root = fact_intake_eval_root(slice_dir)
        journal = load_journal(admission_root)
        if journal is None:
            return {"ok": True, "aborted": False}
        evaluate_round = int(journal.get("candidate_round") or 1)
        if not can_abort_admission(
            journal=journal,
            token=token,
            evaluate_state_path=evaluate_state_path(slice_dir),
            operations_path=evaluate_dir(slice_dir, evaluate_round)
            / "eval-operations.json",
        ):
            return {"ok": False, "error": "admission abort refused"}
        discard_published_snapshot(evaluate_dir(slice_dir, evaluate_round))
        runtime = self._runtime(cycle_id, project_root)
        previous = str(journal.get("previous_phase") or "")
        if (
            str(journal.get("status")) == "transitioned"
            and previous not in {"evaluating", "Evaluating"}
        ):
            runtime["focus_phase"] = previous or "pending"
            runtime["evaluate_round"] = max(0, evaluate_round - 1)
        lease_id = str(journal.get("lease_id") or runtime.get("active_lease_id") or "")
        discard_lease_dir(admission_root / "staging", lease_id)
        runtime["active_lease_id"] = ""
        runtime["write_staging_dir"] = ""
        self._save_runtime(cycle_id, project_root, runtime)
        discard_staging(admission_root, token)
        delete_journal(admission_root)
        return {"ok": True, "aborted": True}

    def enter_evaluating(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        admission_token: str | None = None,
    ) -> dict[str, Any]:
        """Enter Fact-intake-eval phase without compose StageGate / delivery Evaluating."""
        slice_dir = _slice_dir(cycle_id, project_root)
        runtime = self._runtime(cycle_id, project_root)
        if hard_blocked(runtime):
            return {
                "ok": False,
                "current_state": "Working",
                "transitioned": False,
                "error": (
                    "fact-intake Eval hard-blocked: failure_count="
                    f"{runtime.get('failure_count')} >= max_rounds="
                    f"{runtime.get('max_rounds')}"
                ),
                "resume": {
                    "entry": "Deductive",
                    "action": "Fact-intake eval max rounds exhausted",
                },
            }

        already = runtime.get("focus_phase") == "evaluating"
        runtime = enter_evaluating_runtime(runtime)
        evaluate_round = int(runtime["evaluate_round"])
        evaluate_dir(slice_dir, evaluate_round).mkdir(parents=True, exist_ok=True)
        self._save_runtime(cycle_id, project_root, runtime)
        if admission_token:
            mark_transitioned(
                fact_intake_eval_root(slice_dir),
                token=admission_token,
                provider_state_fingerprint=self._provider_fingerprint(slice_dir),
            )
        return {
            "ok": True,
            "current_state": "Working",
            "transitioned": not already,
            "evaluate_round": evaluate_round,
            "focus": str(slice_dir.name),
        }

    def _provider_fingerprint(self, slice_dir: Path) -> str:
        path = runtime_path(slice_dir)
        if not path.is_file():
            return fingerprint_parts(str(slice_dir))
        return stable_runtime_fingerprint(load_runtime(path))

    def request_eval_handoff(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        require_evaluating: bool = True,
    ) -> dict[str, Any]:
        slice_dir = _slice_dir(cycle_id, project_root)
        runtime = self._runtime(cycle_id, project_root)
        if require_evaluating and runtime.get("focus_phase") != "evaluating":
            raise ValueError("fact-intake EvalHandoff requires focus_phase=evaluating")
        if hard_blocked(runtime):
            raise ValueError("fact-intake Eval hard-blocked (max rounds)")

        runtime = allocate_lease(slice_dir, runtime)
        self._save_runtime(cycle_id, project_root, runtime)

        evaluate_round = int(runtime.get("evaluate_round") or 1)
        es_path = evaluate_state_path(slice_dir)
        target = facts_path(slice_dir).resolve()
        if not target.is_file():
            raise ValueError(f"_facts.json missing: {target}")
        source = _source_path(_revision_dir(cycle_id, project_root))

        handoff = build_eval_handoff_v2(
            workflow_id=_WORKFLOW_ID,
            cycle_id=cycle_id,
            session_key=str(slice_dir.name),
            evaluate_round=evaluate_round,
            evaluate_state_path=es_path.resolve().as_posix(),
            evaluate_dir=evaluate_dir(slice_dir, evaluate_round).resolve().as_posix(),
            write_staging_dir=str(runtime["write_staging_dir"]),
            lease_id=str(runtime["active_lease_id"]),
            bindings={
                "eval_target_path": target.as_posix(),
                "facts_path": target.as_posix(),
                "scope_doc": source,
                "source_path": source,
            },
            policy_context={
                "mode": "tech",
                "cycle_type": "feature",
                "upstream_baseline_ref": "",
                "completion_mode": "return_to_caller",
                "eval_capability": _EVAL_CAPABILITY,
            },
        )
        errors = validate_eval_handoff_v2(handoff)
        if errors:
            raise ValueError("; ".join(errors))
        return handoff

    def commit_eval_artifacts(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        errors = validate_artifact_manifest_v2(manifest)
        if errors:
            return {"ok": False, "error": "; ".join(errors)}
        slice_dir = _slice_dir(cycle_id, project_root)
        runtime = self._runtime(cycle_id, project_root)
        if str(manifest.get("lease_id", "")) != str(runtime.get("active_lease_id", "")):
            return {"ok": False, "error": "lease_id mismatch"}

        staging = Path(str(runtime["write_staging_dir"]))
        staged = staging / str(manifest["staged_relative_path"])
        if not staged.is_file():
            return {"ok": False, "error": f"staged artifact missing: {staged}"}
        digest = _file_digest(staged)
        if digest != str(manifest.get("artifact_digest", "")):
            return {"ok": False, "error": "artifact digest mismatch"}

        evaluate_round = int(manifest["evaluate_round"])
        final = evaluate_dir(slice_dir, evaluate_round) / str(
            manifest["final_relative_path"]
        )
        final.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged, final)

        state_patch = manifest.get("state_patch") or {}
        if state_patch:
            es_path = evaluate_state_path(slice_dir)
            data = load_evaluate_state(es_path)
            data.update({str(k): str(v) for k, v in state_patch.items()})
            save_evaluate_state(es_path, data, merge=True)
        return {"ok": True}

    def commit_evaluate_state(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        staged_state_path: Path,
        set_phase_evaluating: bool = False,
        previous_done_required: bool = False,
    ) -> dict[str, Any]:
        del set_phase_evaluating, previous_done_required
        if not staged_state_path.is_file():
            return {"ok": False, "error": f"staged state missing: {staged_state_path}"}
        es_path = evaluate_state_path(_slice_dir(cycle_id, project_root))
        es_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged_state_path, es_path)
        return {"ok": True}

    def read_eval_target_digest(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        target_path: Path,
    ) -> str:
        del cycle_id, project_root
        return _file_digest(Path(target_path))

    def commit_eval_target(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        staged_target_path: Path,
        base_digest: str,
        lease_id: str,
    ) -> dict[str, Any]:
        slice_dir = _slice_dir(cycle_id, project_root)
        runtime = self._runtime(cycle_id, project_root)
        if lease_id != str(runtime.get("active_lease_id", "")):
            return {"ok": False, "error": "lease_id mismatch"}
        staging = Path(str(runtime.get("write_staging_dir") or ""))
        if not staging.is_dir():
            return {"ok": False, "error": "lease staging missing"}
        staged = staged_target_path.resolve()
        try:
            staged.relative_to(staging.resolve())
        except ValueError:
            return {"ok": False, "error": "staged target is outside Eval lease staging"}
        if not staged.is_file():
            return {"ok": False, "error": f"staged target missing: {staged}"}
        target = facts_path(slice_dir).resolve()
        if not target.is_file():
            return {"ok": False, "error": f"target document missing: {target}"}
        if _file_digest(target) != base_digest:
            return {"ok": False, "error": "target base digest mismatch"}
        try:
            replacement = target.with_name(target.name + ".eval-remediation.tmp")
            shutil.copy2(staged, replacement)
            _atomic_replace(replacement, target)
        except OSError as exc:
            return {"ok": False, "error": f"target publish failed: {exc}"}
        return {
            "ok": True,
            "target_path": target.as_posix(),
            "target_digest": _file_digest(target),
        }

    def restore_eval_target(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        snapshot_path: Path,
        expected_current_digest: str,
        lease_id: str,
    ) -> dict[str, Any]:
        slice_dir = _slice_dir(cycle_id, project_root)
        runtime = self._runtime(cycle_id, project_root)
        if lease_id != str(runtime.get("active_lease_id", "")):
            return {"ok": False, "error": "lease_id mismatch"}
        if not snapshot_path.is_file():
            return {"ok": False, "error": f"snapshot missing: {snapshot_path}"}
        target = facts_path(slice_dir).resolve()
        if not target.is_file() or _file_digest(target) != expected_current_digest:
            return {
                "ok": False,
                "error": "cas_rejected: live digest is not expected_current",
            }
        try:
            replacement = target.with_name(target.name + ".eval-restore.tmp")
            shutil.copy2(snapshot_path, replacement)
            _atomic_replace(replacement, target)
        except OSError as exc:
            return {"ok": False, "error": f"target restore failed: {exc}"}
        return {
            "ok": True,
            "target_path": target.as_posix(),
            "target_digest": _file_digest(target),
        }

    def discard_eval_staging(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        lease_id: str,
    ) -> dict[str, Any]:
        runtime = self._runtime(cycle_id, project_root)
        staging = runtime.get("write_staging_dir") or ""
        if staging and Path(staging).name == lease_id:
            shutil.rmtree(staging, ignore_errors=True)
        runtime["active_lease_id"] = ""
        runtime["write_staging_dir"] = ""
        self._save_runtime(cycle_id, project_root, runtime)
        return {"ok": True}
