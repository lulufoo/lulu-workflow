#!/usr/bin/env python3
"""lulu-decision WorkflowAdapter for formal Eval at DC."""

from __future__ import annotations

import hashlib
import json
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

from corpus_compose import (  # noqa: E402
    compose_corpus,
    corpus_fingerprint,
    is_composed_corpus_ref,
    load_dimension_def,
)
from corpus_schema import corpus_ref, dispatch_ids  # noqa: E402
from dec_domain_constraints_schema import KERNEL_STAGE, load_domain_constraints  # noqa: E402
from dec_eval_runtime_schema import (  # noqa: E402
    allocate_lease,
    enter_evaluating_runtime,
    evaluate_dir,
    evaluate_state_path,
    exit_evaluating_runtime,
    hard_blocked,
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
from evaluate_state_schema import (  # noqa: E402
    build_initial_evaluate_state,
    load_evaluate_state,
    save_evaluate_state,
)
from workflow_adapter import SessionContext  # noqa: E402

_WORKFLOW_ID = "lulu-decision"
_CORPUS_ID = "lulu-decision-composed"
_CORPUS_VERSION = "1"
_CORPUS_REF = f"{_CORPUS_ID}@{_CORPUS_VERSION}"
_DIMENSION_ORDER = ("decision-consistency",)


def _init_evaluate_state(
    path: Path,
    corpus: dict[str, Any],
    *,
    evaluate_round: int,
    focus_l: str,
) -> None:
    """Init evaluate-state without importing Compose discussion_pointer helpers."""
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
                "carry_forward_ref": "",
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

    def enter_evaluating(
        self, cycle_id: str, project_root: Path
    ) -> dict[str, Any]:
        paths = self._paths(cycle_id, project_root)
        session_dir = paths["session_dir"]
        runtime = load_runtime(runtime_path(session_dir))
        if hard_blocked(runtime):
            return {
                "ok": False,
                "current_state": "Working",
                "transitioned": False,
                "error": (
                    f"decision Eval hard-blocked: failure_count="
                    f"{runtime.get('failure_count')} >= max_rounds"
                ),
                "resume": {
                    "entry": "DC",
                    "action": "Eval max rounds exhausted; Realign or abort session",
                },
            }

        gate_state = load_gate_state(paths["gate_state"])
        if str(gate_state.get("active_gate", "")) != "DC":
            return {
                "ok": False,
                "current_state": "Working",
                "transitioned": False,
                "error": (
                    f"active_gate is {gate_state.get('active_gate')!r}, expected 'DC'"
                ),
            }

        constraints = load_domain_constraints(paths["domain_constraints"])
        r_closed = is_gate_closed(gate_state, "R")
        try:
            render_and_save_eval_target(
                session_dir,
                cycle_id=cycle_id,
                stage=str(constraints.get("stage") or KERNEL_STAGE),
                constraints=constraints,
                r_gate_closed=r_closed,
            )
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
        eval_dir = evaluate_dir(session_dir, evaluate_round)
        eval_dir.mkdir(parents=True, exist_ok=True)
        es_path = evaluate_state_path(session_dir)
        if not already:
            _init_evaluate_state(
                es_path,
                self.resolve_eval_corpus(cycle_id, project_root),
                evaluate_round=evaluate_round,
                focus_l="DC",
            )
        self._save_runtime(cycle_id, project_root, runtime)
        return {
            "ok": True,
            "current_state": "Working",
            "transitioned": not already,
            "evaluate_round": evaluate_round,
            "focus": "DC",
        }

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
        if hard_blocked(runtime):
            raise ValueError("decision Eval hard-blocked (max rounds)")

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

    def finalize_eval_outcome(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        outcome: str,
        issues: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Decision exit: mark evaluate-state done and leave evaluating."""
        session_dir = self._session_dir(cycle_id, project_root)
        runtime = load_runtime(runtime_path(session_dir))
        es_path = evaluate_state_path(session_dir)
        if es_path.is_file():
            data = load_evaluate_state(es_path)
            # Mark every dimension complete so shared complete-round is unused.
            status = json.loads(data.get("dimension_status") or "{}")
            if isinstance(status, dict):
                for key in list(status):
                    status[key] = "complete"
                data["dimension_status"] = json.dumps(status, separators=(",", ":"))
            data["fix_phase"] = "done"
            data["eval_status"] = "done"
            save_evaluate_state(es_path, data, merge=False)

        failed = outcome == "fail"
        runtime = exit_evaluating_runtime(
            runtime,
            outcome=outcome,
            increment_failure=failed,
        )
        self._save_runtime(cycle_id, project_root, runtime)
        blocked = hard_blocked(runtime)
        return {
            "ok": True,
            "outcome": outcome,
            "failure_count": int(runtime.get("failure_count") or 0),
            "evaluate_round": int(runtime.get("evaluate_round") or 0),
            "hard_blocked": blocked,
            "issues": issues or [],
        }
