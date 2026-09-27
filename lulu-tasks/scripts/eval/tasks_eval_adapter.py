#!/usr/bin/env python3
"""lulu-tasks WorkflowAdapter. One dimension per probe-only round."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parents[1]
_WORKFLOW_ROOT = Path(__file__).resolve().parents[3]
_EVAL_SCRIPTS = _WORKFLOW_ROOT / "eval" / "scripts"
for _path in (_SCRIPTS, _EVAL_SCRIPTS, Path(__file__).resolve().parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from eval_path import ensure_eval_script_layers  # noqa: E402

ensure_eval_script_layers()

from corpus_composition import compose_corpus, load_dimension_def  # noqa: E402
from eval_admission import file_digest, fingerprint_parts, stable_runtime_fingerprint  # noqa: E402
from tasks_eval_admission import (  # noqa: E402
    abort_eval_admission,
    enter_evaluating,
    prepare_eval_admission,
)
from tasks_eval_publish import (  # noqa: E402
    commit_eval_artifacts,
    commit_evaluate_state,
    discard_eval_staging,
    finalize_eval_outcome,
    read_eval_target_digest,
    request_eval_handoff,
)
from tt_eval_runtime_schema import (  # noqa: E402
    PHASES,
    evaluate_dir,
    evaluate_state_path,
    load_runtime,
    load_workflow_state_view,
    runtime_path,
    save_runtime,
    workflow_state_path,
    write_workflow_state_file,
)
from tt_eval_target_schema import eval_target_path, render_and_save_eval_target  # noqa: E402
from tt_workflow_common import (  # noqa: E402
    CACHE_DIR,
    CACHE_SUBDIR,
    parse_frontmatter_fields,
    read_md_field,
    read_md_state,
)
from workflow_adapter import SessionContext  # noqa: E402

_WORKFLOW_ID = "lulu-tasks"
_CORPUS_ID = "lulu-tasks-composed"
_CORPUS_VERSION = "1"
_CORPUS_REF = f"{_CORPUS_ID}@{_CORPUS_VERSION}"


class TasksEvalAdapter:
    """Probe-only adapter. The corpus contains the current phase only."""

    WORKFLOW_ID = _WORKFLOW_ID
    EVAL_CAPABILITY = "probe-only"

    def workflow_root(self) -> Path:
        return _WORKFLOW_ROOT

    def method_roots(self) -> list[Path]:
        return [_WORKFLOW_ROOT, _WORKFLOW_ROOT.parent]

    def session_dir(self, cycle_id: str, project_root: Path) -> Path:
        base = project_root / CACHE_DIR / cycle_id / CACHE_SUBDIR
        active = read_md_field(base / "session-state.md", "active_doc", default="1")
        try:
            doc_round = int(active or "1")
        except ValueError as exc:
            raise ValueError(f"active_doc is not an integer: {active!r}") from exc
        session_dir = base / f"r{doc_round}"
        if not session_dir.is_dir():
            raise FileNotFoundError(f"lulu-tasks round not found: {session_dir}")
        return session_dir

    def save_runtime(self, cycle_id: str, project_root: Path, runtime: dict[str, Any]) -> None:
        session_dir = self.session_dir(cycle_id, project_root)
        save_runtime(runtime_path(session_dir), runtime)
        write_workflow_state_file(workflow_state_path(session_dir), runtime)

    def _tech_ref(self, session_dir: Path) -> str:
        return read_md_field(session_dir / "workflow-state.md", "tech_ref")

    def ensure_eval_target(self, cycle_id: str, project_root: Path) -> None:
        session_dir = self.session_dir(cycle_id, project_root)
        render_and_save_eval_target(session_dir, tech_ref=self._tech_ref(session_dir))

    def provider_fingerprint(self, session_dir: Path) -> str:
        path = runtime_path(session_dir)
        if not path.is_file():
            return fingerprint_parts("")
        return stable_runtime_fingerprint(load_runtime(path))

    def resolve_workflow_state_path(self, cycle_id: str, project_root: Path) -> Path:
        return workflow_state_path(self.session_dir(cycle_id, project_root))

    def load_workflow_state(self, cycle_id: str, project_root: Path) -> dict[str, str]:
        session_dir = self.session_dir(cycle_id, project_root)
        current = read_md_state(session_dir / "workflow-state.md", default="Drafting")
        if current != "Evaluating":
            fields = parse_frontmatter_fields(
                (session_dir / "workflow-state.md").read_text(encoding="utf-8")
            ) if (session_dir / "workflow-state.md").is_file() else {}
            return {
                "version": "1",
                "workflow": _WORKFLOW_ID,
                "mode": "tech",
                "cycle_type": "feature",
                "current_state": current,
                "evaluate_round": str(fields.get("evaluate_round") or "0"),
                "updated_at": "",
            }
        return load_workflow_state_view(load_runtime(runtime_path(session_dir)))

    def save_workflow_state(
        self,
        cycle_id: str,
        project_root: Path,
        updates: dict[str, str],
        *,
        merge: bool = True,
    ) -> None:
        del merge
        runtime = load_runtime(runtime_path(self.session_dir(cycle_id, project_root)))
        if "evaluate_round" in updates:
            runtime["evaluate_round"] = int(updates["evaluate_round"] or 0)
        self.save_runtime(cycle_id, project_root, runtime)

    def resolve_evaluate_state_path(self, cycle_id: str, project_root: Path) -> Path:
        return evaluate_state_path(self.session_dir(cycle_id, project_root))

    def session_context(self, cycle_id: str, project_root: Path) -> SessionContext:
        session_dir = self.session_dir(cycle_id, project_root)
        runtime = load_runtime(runtime_path(session_dir))
        active_raw = read_md_field(
            session_dir.parent / "session-state.md",
            "active_doc",
            default="1",
        )
        return SessionContext(
            active_doc=int(active_raw or "1"),
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
        session_dir = self.session_dir(cycle_id, project_root)
        target = eval_target_path(session_dir).resolve()
        return {
            "eval_target_path": target.as_posix(),
            "compose_doc": target.as_posix(),
            "evaluate_state": es_path.resolve().as_posix(),
            "evaluate_dir": evaluate_dir(session_dir, evaluate_round).resolve().as_posix(),
        }

    def corpus_ref_for_mode(self, mode: str) -> str:
        del mode
        return _CORPUS_REF

    def dimension_defs_dir(self) -> Path:
        return _WORKFLOW_ROOT / "lulu-tasks" / "eval" / "dimension-defs"

    def resolve_eval_corpus(self, cycle_id: str, project_root: Path) -> dict[str, Any]:
        runtime = load_runtime(runtime_path(self.session_dir(cycle_id, project_root)))
        phase = str(runtime.get("phase") or PHASES[0])
        if phase not in PHASES:
            raise ValueError(f"unknown tasks eval phase: {phase}")
        dimension = load_dimension_def(self.dimension_defs_dir() / f"{phase}.json")
        return compose_corpus(
            corpus_id=_CORPUS_ID,
            corpus_version=_CORPUS_VERSION,
            scope="lulu-tasks",
            dimensions=[dimension],
            review_output_prefix="tasks-review",
        )

    def corpus_bind_extensions(self, cycle_id: str, project_root: Path) -> dict[str, str]:
        del cycle_id, project_root
        return {}

    def detect_cycle_type(self, cycle_id: str) -> str:
        del cycle_id
        return "feature"

    def eval_admission_context(self, cycle_id: str, project_root: Path):
        from eval_admission import EvalAdmissionContext

        session_dir = self.session_dir(cycle_id, project_root)
        self.ensure_eval_target(cycle_id, project_root)
        runtime = load_runtime(runtime_path(session_dir))
        target = eval_target_path(session_dir).resolve()
        current = int(runtime.get("evaluate_round") or 0)
        already = runtime.get("focus_phase") == "evaluating"
        return EvalAdmissionContext(
            admission_root=session_dir,
            session_key="tasks",
            provider_state_fingerprint=self.provider_fingerprint(session_dir),
            previous_phase=str(runtime.get("focus_phase") or "pending"),
            target_path=target,
            target_digest=file_digest(target),
            candidate_round=current if already and current >= 1 else current + 1,
        )

    def prepare_eval_admission(self, cycle_id: str, project_root: Path) -> dict[str, Any]:
        return prepare_eval_admission(self, cycle_id, project_root)

    def abort_eval_admission(self, cycle_id: str, project_root: Path, *, token: str) -> dict[str, Any]:
        return abort_eval_admission(self, cycle_id, project_root, token=token)

    def enter_evaluating(
        self,
        cycle_id: str,
        project_root: Path,
        *,
        admission_token: str | None = None,
    ) -> dict[str, Any]:
        return enter_evaluating(self, cycle_id, project_root, admission_token=admission_token)

    def request_eval_handoff(self, cycle_id: str, project_root: Path, *, require_evaluating: bool = True) -> dict[str, Any]:
        return request_eval_handoff(self, cycle_id, project_root, require_evaluating=require_evaluating)

    def commit_eval_artifacts(self, cycle_id: str, project_root: Path, *, manifest: dict[str, Any]) -> dict[str, Any]:
        return commit_eval_artifacts(self, cycle_id, project_root, manifest=manifest)

    def commit_evaluate_state(self, cycle_id: str, project_root: Path, *, staged_state_path: Path, set_phase_evaluating: bool = False, previous_done_required: bool = False) -> dict[str, Any]:
        return commit_evaluate_state(self, cycle_id, project_root, staged_state_path=staged_state_path, set_phase_evaluating=set_phase_evaluating, previous_done_required=previous_done_required)

    def read_eval_target_digest(self, cycle_id: str, project_root: Path, *, target_path: Path) -> str:
        del cycle_id, project_root
        return read_eval_target_digest(target_path)

    def discard_eval_staging(self, cycle_id: str, project_root: Path, *, lease_id: str) -> dict[str, Any]:
        return discard_eval_staging(self, cycle_id, project_root, lease_id=lease_id)

    def finalize_eval_outcome(self, cycle_id: str, project_root: Path, *, outcome: str, issues: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        return finalize_eval_outcome(self, cycle_id, project_root, outcome=outcome, issues=issues)
