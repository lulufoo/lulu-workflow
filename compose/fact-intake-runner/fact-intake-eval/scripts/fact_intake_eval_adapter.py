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
_COMPOSE_CORE = _WORKFLOW_ROOT / "compose" / "scripts" / "core"
_COMPOSE_SECTION = _WORKFLOW_ROOT / "compose" / "scripts" / "section"
_COMPOSE_SCHEMA_SESSION = (
    _WORKFLOW_ROOT / "compose" / "scripts" / "schema" / "session"
)
# Compose schema/session also ships eval_handoff_schema.py — keep Eval scripts
# ahead of that directory so the shared Eval handoff helpers win.
for p in (
    _INTAKE_EVAL_SCRIPTS,
    _COMPOSE_CORE,
    _COMPOSE_SECTION,
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
    hard_blocked,
    load_runtime,
    load_workflow_state_view,
    runtime_path,
    save_runtime,
    workflow_state_view_path,
    write_workflow_state_file,
)
from compose_session import workflow_state_path as compose_workflow_state_path  # noqa: E402
from corpus_compose import (  # noqa: E402
    compose_corpus,
    corpus_fingerprint,
    is_composed_corpus_ref,
    load_dimension_def,
)
from corpus_schema import corpus_ref, dispatch_ids  # noqa: E402
from discussion_pointer_schema import active_slice_dir  # noqa: E402
from eval_handoff_schema import (  # noqa: E402
    build_eval_handoff_v2,
    validate_artifact_manifest_v2,
    validate_eval_handoff_v2,
)
from evaluate_state_schema import (  # noqa: E402
    build_initial_evaluate_state,
    load_evaluate_state,
    save_evaluate_state,
)
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
_CORPUS_VERSION = "1"
_CORPUS_REF = f"{_CORPUS_ID}@{_CORPUS_VERSION}"
_DIMENSION_ORDER = ("e1-doc-coverage", "e2-fact-provenance")
_PROFILE_ENV = "COMPOSE_FACT_INTAKE_PROFILE_ID"


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


def _init_evaluate_state(
    path: Path,
    corpus: dict[str, Any],
    *,
    evaluate_round: int,
    focus_l: str,
) -> None:
    ids = dispatch_ids(corpus)
    ref = corpus_ref(corpus)
    fingerprint = ""
    if is_composed_corpus_ref(ref):
        fingerprint = corpus_fingerprint(ids, cycle_type="feature")
    save_evaluate_state(
        path,
        build_initial_evaluate_state(
            dimension_ids=ids,
            corpus_ref=ref,
            corpus_fingerprint=fingerprint,
            dimension_dispatch=str(corpus.get("dimension_dispatch", "parallel")),
            evaluate_round=evaluate_round,
            focus_l=focus_l,
        ),
        merge=False,
    )


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
                    "carry_forward_ref": "",
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

    def enter_evaluating(
        self, cycle_id: str, project_root: Path
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
        eval_round_dir = evaluate_dir(slice_dir, evaluate_round)
        eval_round_dir.mkdir(parents=True, exist_ok=True)
        es_path = evaluate_state_path(slice_dir)
        if not already:
            _init_evaluate_state(
                es_path,
                self.resolve_eval_corpus(cycle_id, project_root),
                evaluate_round=evaluate_round,
                focus_l=str(slice_dir.name),
            )
        self._save_runtime(cycle_id, project_root, runtime)
        return {
            "ok": True,
            "current_state": "Working",
            "transitioned": not already,
            "evaluate_round": evaluate_round,
            "focus": str(slice_dir.name),
        }

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

    def commit_remediation_target(
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

    def restore_remediation_target(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        snapshot_path: Path,
        expected_digest: str,
        lease_id: str,
    ) -> dict[str, Any]:
        slice_dir = _slice_dir(cycle_id, project_root)
        runtime = self._runtime(cycle_id, project_root)
        if lease_id != str(runtime.get("active_lease_id", "")):
            return {"ok": False, "error": "lease_id mismatch"}
        if not snapshot_path.is_file():
            return {"ok": False, "error": f"snapshot missing: {snapshot_path}"}
        target = facts_path(slice_dir).resolve()
        try:
            replacement = target.with_name(target.name + ".eval-restore.tmp")
            shutil.copy2(snapshot_path, replacement)
            _atomic_replace(replacement, target)
        except OSError as exc:
            return {"ok": False, "error": f"target restore failed: {exc}"}
        digest = _file_digest(target)
        if digest != expected_digest:
            return {"ok": False, "error": "restored digest mismatch"}
        return {"ok": True, "target_path": target.as_posix(), "target_digest": digest}

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
