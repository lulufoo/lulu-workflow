#!/usr/bin/env python3
"""lulu-decision WorkflowAdapter for formal Eval at DC."""

from __future__ import annotations

import hashlib
import shutil
import sys
from pathlib import Path
from typing import Any

_DECISION_SCRIPTS = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_EVAL_SCRIPTS = _WORKFLOW_ROOT / "eval" / "scripts"
for p in (_DECISION_SCRIPTS, _EVAL_SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
from eval_path import ensure_eval_script_layers  # noqa: E402

ensure_eval_script_layers()

from corpus_composition import compose_corpus, load_dimension_def  # noqa: E402
from dec_domain_constraints_schema import KERNEL_STAGE, load_domain_constraints  # noqa: E402
from dec_eval_runtime_schema import (  # noqa: E402
    allocate_lease,
    enter_evaluating_runtime,
    evaluate_dir,
    evaluate_state_path,
    exit_evaluating_runtime,
    load_runtime,
    load_workflow_state_view,
    runtime_path,
    save_runtime,
    workflow_state_path,
    write_workflow_state_file,
)
from dec_eval_target_schema import (  # noqa: E402
    eval_target_path,
    render_and_save_eval_target,
)
from dec_gate_state_schema import is_gate_closed, load_gate_state  # noqa: E402
from dec_session_paths import (  # noqa: E402
    find_session_dir,
    session_artifact_paths,
)
from dec_session_state_schema import read_current_state  # noqa: E402
from dec_workflow_common import CACHE_DIR  # noqa: E402
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
from workflow_adapter import SessionContext  # noqa: E402

_WORKFLOW_ID = "lulu-decision"
_CORPUS_ID = "lulu-decision-composed"
_CORPUS_VERSION = "2"
_CORPUS_REF = f"{_CORPUS_ID}@{_CORPUS_VERSION}"
_DIMENSION_ORDER = ("decision-consistency",)
_EVAL_CAPABILITY = "probe-only"


class DecisionEvalAdapter:
    """WorkflowAdapter for Decision DC Eval (probe-only exit to RS)."""

    WORKFLOW_ID = _WORKFLOW_ID

    def _session_dir(self, cycle_id: str, project_root: Path) -> Path:
        found = find_session_dir(project_root, cycle_id, KERNEL_STAGE, CACHE_DIR)
        if found is None:
            # Holder stages store domain-constraints.stage as holder id.
            cycle_base = project_root / CACHE_DIR / cycle_id
            if cycle_base.is_dir():
                for sub in sorted(cycle_base.iterdir()):
                    if not sub.is_dir():
                        continue
                    dc = sub / "domain-constraints.json"
                    if dc.is_file():
                        return sub
                    main = sub / "main"
                    if (main / "domain-constraints.json").is_file():
                        return main
            raise FileNotFoundError(
                f"decision session not found for cycle {cycle_id!r}"
            )
        return found

    def _paths(self, cycle_id: str, project_root: Path) -> dict[str, Path]:
        return session_artifact_paths(self._session_dir(cycle_id, project_root))

    def _runtime(self, cycle_id: str, project_root: Path) -> dict[str, Any]:
        session_dir = self._session_dir(cycle_id, project_root)
        return load_runtime(runtime_path(session_dir))

    def _save_runtime(
        self, cycle_id: str, project_root: Path, runtime: dict[str, Any]
    ) -> None:
        session_dir = self._session_dir(cycle_id, project_root)
        save_runtime(runtime_path(session_dir), runtime)
        write_workflow_state_file(workflow_state_path(session_dir), runtime)

    def resolve_workflow_state_path(
        self, cycle_id: str, project_root: Path
    ) -> Path:
        return workflow_state_path(self._session_dir(cycle_id, project_root))

    def load_workflow_state(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, str]:
        session_dir = self._session_dir(cycle_id, project_root)
        session_state = read_current_state(session_dir / "session-state.md")
        if session_state not in frozenset({"InProgress", "Frozen"}):
            # Eval control expects Working; expose blocking state via non-Working.
            return {
                "version": "1",
                "workflow": _WORKFLOW_ID,
                "mode": "tech",
                "cycle_type": "feature",
                "current_state": session_state,
                "evaluate_round": "0",
                "updated_at": "",
            }
        runtime = self._runtime(cycle_id, project_root)
        return load_workflow_state_view(runtime)

    def save_workflow_state(
        self,
        cycle_id: str,
        project_root: Path,
        updates: dict[str, str],
        *,
        merge: bool = True,
    ) -> None:
        runtime = self._runtime(cycle_id, project_root)
        if "evaluate_round" in updates:
            runtime["evaluate_round"] = int(updates["evaluate_round"] or 0)
        self._save_runtime(cycle_id, project_root, runtime)

    def resolve_evaluate_state_path(
        self, cycle_id: str, project_root: Path
    ) -> Path:
        return evaluate_state_path(self._session_dir(cycle_id, project_root))

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
        session_dir = self._session_dir(cycle_id, project_root)
        target = eval_target_path(session_dir).resolve()
        return {
            "eval_target_path": target.as_posix(),
            "compose_doc": target.as_posix(),
            "evaluate_state": es_path.resolve().as_posix(),
            "evaluate_dir": evaluate_dir(session_dir, evaluate_round)
            .resolve()
            .as_posix(),
        }

    def corpus_ref_for_mode(self, mode: str) -> str:
        del mode
        return _CORPUS_REF

    def dimension_defs_dir(self) -> Path:
        return _WORKFLOW_ROOT / "decision" / "eval" / "dimension-defs"

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
            scope="lulu-decision",
            dimensions=dimensions,
            review_output_prefix="decision-review",
        )

    def corpus_bind_extensions(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, str]:
        del cycle_id, project_root
        return {}

    def detect_cycle_type(self, cycle_id: str) -> str:
        del cycle_id
        return "feature"

    def eval_admission_context(
        self, cycle_id: str, project_root: Path
    ) -> EvalAdmissionContext:
        session_dir = self._session_dir(cycle_id, project_root)
        self._ensure_eval_target(cycle_id, project_root)
        runtime = load_runtime(runtime_path(session_dir))
        target = eval_target_path(session_dir).resolve()
        current = int(runtime.get("evaluate_round") or 0)
        already = runtime.get("focus_phase") == "evaluating"
        return EvalAdmissionContext(
            admission_root=session_dir,
            session_key="DC",
            provider_state_fingerprint=self._provider_fingerprint(session_dir),
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
            corpus = expand_corpus(
                self.resolve_eval_corpus(cycle_id, project_root),
                {
                    "eval_target_path": ctx.target_path.as_posix(),
                    "M": str(ctx.candidate_round),
                },
            )
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
        return {
            "ok": True,
            "token": token,
            "corpus": corpus,
            "skip_reasons": {},
            "snapshot_digest": str(manifest["corpus_digest"]),
            "snapshot_ref": SNAPSHOT_REF,
            "evaluate_dir": evaluate_dir(
                self._session_dir(cycle_id, project_root), ctx.candidate_round
            ).resolve().as_posix(),
            "context": ctx,
        }

    def abort_eval_admission(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        token: str,
    ) -> dict[str, Any]:
        session_dir = self._session_dir(cycle_id, project_root)
        journal = load_journal(session_dir)
        if journal is None:
            return {"ok": True, "aborted": False}
        evaluate_round = int(journal.get("candidate_round") or 1)
        if not can_abort_admission(
            journal=journal,
            token=token,
            evaluate_state_path=evaluate_state_path(session_dir),
            operations_path=evaluate_dir(session_dir, evaluate_round)
            / "eval-operations.json",
        ):
            return {"ok": False, "error": "admission abort refused"}
        discard_published_snapshot(evaluate_dir(session_dir, evaluate_round))
        runtime = load_runtime(runtime_path(session_dir))
        previous = str(journal.get("previous_phase") or "")
        if (
            str(journal.get("status")) == "transitioned"
            and previous not in {"evaluating", "Evaluating"}
        ):
            runtime["focus_phase"] = previous or "pending"
            runtime["evaluate_round"] = max(0, evaluate_round - 1)
        lease_id = str(journal.get("lease_id") or runtime.get("active_lease_id") or "")
        discard_lease_dir(session_dir / "eval" / "staging", lease_id)
        runtime["active_lease_id"] = ""
        runtime["write_staging_dir"] = ""
        self._save_runtime(cycle_id, project_root, runtime)
        discard_staging(session_dir, token)
        delete_journal(session_dir)
        return {"ok": True, "aborted": True}

    def enter_evaluating(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        admission_token: str | None = None,
    ) -> dict[str, Any]:
        paths = self._paths(cycle_id, project_root)
        session_dir = paths["session_dir"]
        runtime = load_runtime(runtime_path(session_dir))
        try:
            self._ensure_eval_target(cycle_id, project_root)
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
        self._save_runtime(cycle_id, project_root, runtime)
        if admission_token:
            mark_transitioned(
                session_dir,
                token=admission_token,
                provider_state_fingerprint=self._provider_fingerprint(session_dir),
            )
        return {
            "ok": True,
            "current_state": "Working",
            "transitioned": not already,
            "evaluate_round": evaluate_round,
            "focus": "DC",
        }

    def _ensure_eval_target(self, cycle_id: str, project_root: Path) -> None:
        paths = self._paths(cycle_id, project_root)
        gate_state = load_gate_state(paths["gate_state"])
        if str(gate_state.get("active_gate", "")) != "DC":
            raise ValueError(
                f"active_gate is {gate_state.get('active_gate')!r}, expected 'DC'"
            )
        constraints = load_domain_constraints(paths["domain_constraints"])
        render_and_save_eval_target(
            paths["session_dir"],
            cycle_id=cycle_id,
            stage=str(constraints.get("stage") or KERNEL_STAGE),
            constraints=constraints,
            r_gate_closed=is_gate_closed(gate_state, "R"),
        )

    def _provider_fingerprint(self, session_dir: Path) -> str:
        parts = []
        runtime = runtime_path(session_dir)
        if runtime.is_file():
            parts.append(stable_runtime_fingerprint(load_runtime(runtime)))
        gate = session_artifact_paths(session_dir)["gate_state"]
        if Path(gate).is_file():
            parts.append(file_digest(Path(gate)))
        return fingerprint_parts(*parts)

    def request_eval_handoff(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        require_evaluating: bool = True,
    ) -> dict[str, Any]:
        session_dir = self._session_dir(cycle_id, project_root)
        runtime = load_runtime(runtime_path(session_dir))
        if require_evaluating and runtime.get("focus_phase") != "evaluating":
            raise ValueError("decision EvalHandoff requires focus_phase=evaluating")

        runtime = allocate_lease(session_dir, runtime)
        self._save_runtime(cycle_id, project_root, runtime)

        evaluate_round = int(runtime.get("evaluate_round") or 1)
        es_path = evaluate_state_path(session_dir)
        target = eval_target_path(session_dir).resolve()
        if not target.is_file():
            raise ValueError(f"decision-eval-target.md missing: {target}")

        handoff = build_eval_handoff_v2(
            workflow_id=_WORKFLOW_ID,
            cycle_id=cycle_id,
            session_key="DC",
            evaluate_round=evaluate_round,
            evaluate_state_path=es_path.resolve().as_posix(),
            evaluate_dir=evaluate_dir(session_dir, evaluate_round).resolve().as_posix(),
            write_staging_dir=str(runtime["write_staging_dir"]),
            lease_id=str(runtime["active_lease_id"]),
            bindings={"eval_target_path": target.as_posix()},
            policy_context={
                "mode": "tech",
                "cycle_type": "feature",
                "upstream_baseline_ref": "",
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
        session_dir = self._session_dir(cycle_id, project_root)
        runtime = load_runtime(runtime_path(session_dir))
        if str(manifest.get("lease_id", "")) != str(runtime.get("active_lease_id", "")):
            return {"ok": False, "error": "lease_id mismatch"}

        staging = Path(str(runtime["write_staging_dir"]))
        staged = staging / str(manifest["staged_relative_path"])
        if not staged.is_file():
            return {"ok": False, "error": f"staged artifact missing: {staged}"}
        digest = hashlib.sha256(staged.read_bytes()).hexdigest()
        if digest != str(manifest.get("artifact_digest", "")):
            return {"ok": False, "error": "artifact digest mismatch"}

        evaluate_round = int(manifest["evaluate_round"])
        final = evaluate_dir(session_dir, evaluate_round) / str(
            manifest["final_relative_path"]
        )
        final.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged, final)

        state_patch = manifest.get("state_patch") or {}
        if state_patch:
            es_path = evaluate_state_path(session_dir)
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
        session_dir = self._session_dir(cycle_id, project_root)
        if not staged_state_path.is_file():
            return {"ok": False, "error": f"staged state missing: {staged_state_path}"}
        es_path = evaluate_state_path(session_dir)
        es_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(staged_state_path, es_path)
        return {"ok": True}

    def discard_eval_staging(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        lease_id: str,
    ) -> dict[str, Any]:
        session_dir = self._session_dir(cycle_id, project_root)
        runtime = load_runtime(runtime_path(session_dir))
        staging = runtime.get("write_staging_dir") or ""
        if staging and Path(staging).name == lease_id:
            shutil.rmtree(staging, ignore_errors=True)
        runtime["active_lease_id"] = ""
        runtime["write_staging_dir"] = ""
        self._save_runtime(cycle_id, project_root, runtime)
        return {"ok": True}

    def read_eval_target_digest(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        target_path: Path,
    ) -> str:
        del cycle_id, project_root
        return hashlib.sha256(Path(target_path).read_bytes()).hexdigest()

    def finalize_eval_outcome(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        outcome: str,
        issues: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Decision runtime exit after Eval Control complete-probe-only."""
        session_dir = self._session_dir(cycle_id, project_root)
        runtime = load_runtime(runtime_path(session_dir))
        runtime = exit_evaluating_runtime(runtime, outcome=outcome)
        self._save_runtime(cycle_id, project_root, runtime)
        return {
            "ok": True,
            "outcome": outcome,
            "evaluate_round": int(runtime.get("evaluate_round") or 0),
            "issues": issues or [],
        }
